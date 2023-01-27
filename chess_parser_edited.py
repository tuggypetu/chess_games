#!/usr/bin/env python
# coding: utf-8

# Import libraries

import json
import os
import re
import urllib.request
from pathlib import Path

import pandas as pd
import requests

import ssl

ssl._create_default_https_context = ssl._create_unverified_context

requests.packages.urllib3.disable_warnings()

# Declare Globals
user = 'sid0049'  # The user for whom the script is intended to run
pgnMeta = ["Event", "Site", "Date", "Round", "White", "Black", "Result", "Tournament",
           "CurrentPosition", "Timezone", "ECO", "ECOURL", "UTCDate", "UTCTime", "WhiteELO",
           "BlackELO", "TimeControl", "Termination", "StartTime", "EndDate", "EndTime", "Link", "Moves"]
tgtFilePath = f"data/{user}_games.csv"  # This is the path where the final CSV gets created
moveStartLine = 22  # Moves in chess.com PGNs typically start from the 22nd line for each game
PGNDirectory = f"data/pgn/{user}"  # This is the location where the API downloads the PGNs from the archives
PGNFile = f"data/pgn/{user}_games.pgn"


def getPGN(user):
    """This function accesses the chess.com public API and downloads all the PGNs to a folder"""
    pgn_archive_links = requests.get("https://api.chess.com/pub/player/" + user + "/games/archives", verify=False)
    if not os.path.exists(PGNDirectory):
        os.makedirs(PGNDirectory)
    for url in json.loads(pgn_archive_links.content)["archives"]:
        filepath = PGNDirectory + "/" + url.split("/")[7] + url.split("/")[8] + '.pgn'
        urllib.request.urlretrieve(url + '/pgn', filepath)
    with open(PGNFile, 'w') as outfile:
        pgn_files = sorted(os.listdir(PGNDirectory))
        for fe in pgn_files:
            with open(f"{PGNDirectory}/{fe}") as infile:
                outfile.write(infile.read())
            os.remove(f"{PGNDirectory}/{fe}")


def importPGNData(filepath):
    """This function returns the data read as a string"""
    with open(filepath) as f:
        return f.readlines()


def getEdgePoints(data):
    """This function returns the start and end indices for each game in the PGN"""
    ends = []
    starts = []
    for n, l in enumerate(data):
        if l.startswith("[Event"):
            if n != 0:
                ends.append(n - 1)
            starts.append(n)
        elif n == len(data) - 1:
            ends.append(n)

    return starts, ends


def grpGames(data, starts, ends):
    """This function groups games into individual lists based on the start and end index"""
    blocks = []
    for i in range(len(ends)):
        element = data[starts[i]: ends[i] + 1]
        if element not in blocks:
            blocks.append(element)

    return blocks


def mergeMoves(game):
    """This function cleans out the moves and other attributes, removes newlines and formats the list to be converted
    into a dictionary"""
    if len(game) == 22:
        game.insert(7, '[Tournament "-"]')
    for n, eachrow in enumerate(game):
        game[n] = game[n].replace('\n', '')
        try:
            if n <= moveStartLine - 1:
                game[n] = stripwhitespace(game[n]).split('~')[1].strip(']["')
        except:
            if n <= moveStartLine - 4:
                game[n] = stripwhitespace(game[n]).split('~')[1].strip(']["')
    return list(filter(None, game))


def stripwhitespace(text):
    lst = text.split('"')
    for i, item in enumerate(lst):
        if not i % 2:
            lst[i] = re.sub("\s+", "~", item)
    return '"'.join(lst)


def createGameDictLetsPlay(game_dict):
    """This is a helper function to address games under Lets Play events on chess.com. These events have a slightly
    different way of representation than the Live Chess events"""
    for n, move in enumerate(game_dict["Moves"].split(" ")):

        if n % 3 == 0:  # every 3rd element is the move number
            if move == '1-0' or move == '0-1' or move == '1/2-1/2':
                None
            else:
                movenum = n
        elif n == movenum + 2:
            if move == '1-0' or move == '0-1' or move == '1/2-1/2':
                None
            else:
                game_dict["whitemoves"].append(move)
        else:
            if move == '1-0' or move == '0-1' or move == '1/2-1/2':
                None
            else:
                game_dict["blackmoves"].append(move)

    if len(game_dict["blackmoves"]) > len(game_dict["whitemoves"]):
        game_dict["whitemoves"].append("over")
    if len(game_dict["blackmoves"]) < len(game_dict["whitemoves"]):
        game_dict["blackmoves"].append("over")
    del game_dict["Moves"]
    return game_dict


def createGameDictLiveChess(game_dict):
    """This is a helper function to address games under Live Chess events on chess.com."""
    try:
        for n, move in enumerate(game_dict["Moves"].split(" ")):

            if '{' in move or '}' in move:
                pass
            elif '.' in move:
                movenum = int(move.split(".")[0])
                if "..." in move:
                    color = 'black'
                else:
                    color = "white"
            else:
                if color == "white":
                    if move == '1-0' or move == '0-1' or move == '1/2-1/2':
                        pass
                    else:
                        game_dict["whitemoves"].append(move)
                else:
                    if move == '1-0' or move == '0-1' or move == '1/2-1/2':
                        pass
                    else:
                        game_dict["blackmoves"].append(move)

        if len(game_dict["blackmoves"]) > len(game_dict["whitemoves"]):
            game_dict["whitemoves"].append("over")
        if len(game_dict["blackmoves"]) < len(game_dict["whitemoves"]):
            game_dict["blackmoves"].append("over")
        del game_dict["Moves"]
    except:
        pass

    return game_dict


def createGameDict(games):
    allgames = []
    for gamenum, eachgame in enumerate(games):
        game_dict = dict(zip(pgnMeta, eachgame))
        movenum = 0
        game_dict["whitemoves"] = []
        game_dict["blackmoves"] = []
        color = "white"
        if game_dict["Event"] == "Let's Play!":
            allgames.append(createGameDictLetsPlay(game_dict))
        else:
            allgames.append(createGameDictLiveChess(game_dict))
    return allgames


def arrange_game_list(games_list):
    """Removes unwanted games from list, and clean data in game list"""
    games = []
    for gg in games_list:
        game = [x.strip() for x in gg if x.strip() != '']
        games.append(game)
    games = [mergeMoves(game) for game in games]
    del_list = []
    for n, oo in enumerate(games):
        if len(oo) == 25 or len(oo) < 22:
            del_list.append(n)
    for index in sorted(del_list, reverse=True):
        del games[index]
    return games


def main():
    getPGN(user)
    try:
        tgtFilePathObj = Path(tgtFilePath)
        tgtFilePathObj.unlink()
    except FileNotFoundError:
        with open(tgtFilePath, "w"):
            tgtFilePathObj = Path(tgtFilePath)
            tgtFilePathObj.unlink()

    data = importPGNData(PGNFile)
    starts, ends = getEdgePoints(data)
    games_n = grpGames(data, starts, ends)
    games = arrange_game_list(games_n)
    df = pd.DataFrame(games, columns=pgnMeta)
    df.to_csv(tgtFilePath, index=False)
    print("Export Complete!")


# Run Program
main()
