#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
@author: ruthbuck
"""

import requests
import json
import re
from bs4 import BeautifulSoup
import pandas as pd


# Functions
def get_boarddoc_meetings(site, committee_id, date=None):
    """
    Scrapes list of meetings for a committee on a BoardDoc site.

    Parameters
    ----------
    site: str
        String including unique BoardDoc site (ex: for Arlington Public Schools, VA BoardDoc site, site = 'vbsa/arlington')

    committee_id: str
        String with unique identifier of BoardDoc committee to scrape. BoardDoc committees are listed in a dropdown menu in the top right hand corner of the page (some districts only have one committee: Main Governing Board). If you inspect the HTML for this dropdown, the committee id will be the value in the option element of the div with id="committee-select".

    date: tuple, optional
        Optional tuple to specify date ranges to scrape. Dates should be a string in the format 'YYYYMMDD'. To scrape all meetings AFTER a certain date, use None in place of a second date (ex: date = ('20241001', None)). To scrape all meetings BEFORE a certain date, use None in place of the first date (ex: date = (None, '20241001')).

    Returns
    -------
    pandas.DataFrame
        A dataframe with columns meeting_id, committee_id, numberdate, and name for each meeting scraped from BoardDocs.
    """
    data = "current_committee_id=" + committee_id
    meetings_url = (
        "https://go.boarddocs.com/{}/Board.nsf/BD-GetMeetingsList?open".format(site)
    )
    response = requests.post(meetings_url, data=data)
    meetings_json = json.loads(response.text)
    meetings = [
        {
            "meeting_id": meeting.get("unique", None),
            "committee_id": committee_id,
            "numberdate": meeting.get("numberdate", None),
            "name": meeting.get("name", None),
        }
        for meeting in meetings_json
    ]
    meetings = pd.DataFrame(meetings)
    meetings.dropna(subset=["meeting_id"], inplace=True)
    if type(date) is tuple:
        if (type(date[0]) is not str) & (type(date[1]) is str):
            meetings = meetings[meetings["numberdate"].astype(int) <= int(date[1])]
        elif (type(date[0]) is str) & (type(date[1]) is not str):
            meetings = meetings[meetings["numberdate"].astype(int) >= int(date[0])]
        elif (type(date[0]) is str) & (type(date[1]) is str):
            meetings = meetings[
                (meetings["numberdate"].astype(int) >= int(date[0]))
                & (meetings["numberdate"].astype(int) <= int(date[1]))
            ]
    return meetings


def process_boarddoc_meeting(site, committee_id, meeting_id):
    """
    Scrapes the agenda data for a BoardDoc meeting.

    Parameters
    ----------
    site: str
        String including unique BoardDoc site (ex: for Arlington Public Schools, VA BoardDoc site, site = 'vbsa/arlington')

    committee_id: str
        String with unique identifier of BoardDoc committee to scrape. BoardDoc committees are listed in a dropdown menu in the top right hand corner of the page (some districts only have one committee: Main Governing Board). If you inspect the HTML for this dropdown, the committee id will be the value in the option element of the div with id="committee-select". 

    meeting_id: str
        String with unique identifier of BoardDoc meeting to scrape.

    Returns
    -------
    dict
        A dictionary with keys meeting_id, name, date, description, items, full_text, and files. Items include a list of all agenda items (strings). Full text is the unparsed HTML scraped from the meeting. Files are a list of tuples, each with the agenda item the file was listed under, the name of the file on BoardDocs, and the file url. Recommended to save this dict as a json. 
    """
    data = "id=" + meeting_id + "&" + "current_committee_id=" + committee_id
    agenda_url = "https://go.boarddocs.com/{}/Board.nsf/PRINT-AgendaDetailed".format(
        site
    )
    response = requests.post(agenda_url, data=data)
    soup = BeautifulSoup(response.content, "html.parser")
    agenda_data = {
        "meeting_id": meeting_id,
        "name": soup.find("div", {"class": "print-meeting-name"}).string,
        "date": soup.find("div", {"class": "print-meeting-date"}).string,
    }
    if type(soup.find("div", {"class": "print-meeting-description"}).string) is str:
        agenda_data["description"] = soup.find(
            "div", {"class": "print-meeting-description"}
        ).string
    else:
        agenda_data["description"] = ""
    agenda_items = []
    for div in soup.find_all("div"):
        if div.has_attr("aria-level"):
            if div.attrs["aria-level"] == "1":
                if div.text not in agenda_items:
                    agenda_items.append(div.text)
        elif div.has_attr("class"):
            if "agendaorder" in div.attrs["class"]:
                agenda_items.append(re.search("(?<=Subject\n).+", div.text)[0])
    agenda_data["items"] = agenda_items
    agenda_data["full_text"] = soup.get_text()
    files = []
    for div in soup.find_all("div", {"class": "public-file"}):
        file = div.findChild("a")
        if file is not None:
            if file.has_attr("href"):
                item = re.search(
                    "(?<=Subject\n).+",
                    div.find_parent("div", {"class": "agendaorder"}).text,
                )[0]
                files.append((item, file.text, file.attrs["href"]))
    for div in soup.find_all("a", href=re.compile("legacy-content")):
        item = re.search(
            "(?<=Subject\n).+", div.find_parent("div", {"class": "agendaorder"}).text
        )[0]
        file = div.findChild()
        if file.has_attr("alt"):
            filename = file["alt"]
        else:
            filename = ""
        files.append((item, filename, div.attrs["href"]))
    agenda_data["files"] = files
    return agenda_data


def process_boarddoc_district(site, committee_ids, date=None):
    """
    Scrapes list of meetings and their agendas for multiple committees on a BoardDoc site.

    Parameters
    ----------
    site: str
        String including unique BoardDoc site (ex: for Arlington Public Schools, VA BoardDoc site, site = 'vbsa/arlington')

    committee_id: list
        List of strings with unique identifiers of BoardDoc committees to scrape. BoardDoc committees are listed in a dropdown menu in the top right hand corner of the page (some districts only have one committee: Main Governing Board). If you inspect the HTML for this dropdown, the committees id will be the values in the option elements of the div with id="committee-select".

    date: tuple, optional
        Optional tuple to specify date ranges to scrape. Dates should be a string in the format 'YYYYMMDD'. To scrape all meetings AFTER a certain date, use None in place of a second date (ex: date = ('20241001', None)). To scrape all meetings BEFORE a certain date, use None in place of the first date (ex: date = (None, '20241001')).

    Returns
    -------
    pandas.DataFrame
        A dataframe with columns meeting_id, committee_id, numberdate, and name for each meeting scraped from BoardDocs.

    list
        A list of dictionaries for each meeting's agenda with keys meeting_id, name, date, description, items, full_text, and files. Items include a list of all agenda items (strings). Full text is the unparsed HTML scraped from the meeting. Files are a list of tuples, each with the agenda item the file was listed under, the name of the file on BoardDocs, and the file url. Recommended to save this dict as a json. 
    """
    if len(committee_ids) == 1:
        meetings = get_boarddoc_meetings(site, committee_ids[0], date)
    elif len(committee_ids) > 1:
        meetings = pd.DataFrame(
            columns=["meeting_id", "committee_id", "numberdate", "name"]
        )
        for committee_id in committee_ids:
            meetings = pd.concat(
                [meetings, get_boarddoc_meetings(site, committee_id, date)]
            )
    meetings.drop_duplicates(subset=["meeting_id"], inplace=True)
    meetings.reset_index(drop=True, inplace=True)
    agendas = []
    for i in range(len(meetings)):
        agendas.append(
            process_boarddoc_meeting(
                site, meetings["committee_id"][i], meetings["meeting_id"][i]
            )
        )
    return (meetings, agendas)


def get_boarddoc_minutes_embed(site, committee_id, meeting_id):
    """
    Scrape text of embedded meeting minutes for a given BoardDoc meeting (if available).

    Parameters
    ----------
    site: str
        String including unique BoardDoc site (ex: for Arlington Public Schools, VA BoardDoc site, site = 'vbsa/arlington')

    committee_id: str
        String with unique identifier of BoardDoc committee to scrape. BoardDoc committees are listed in a dropdown menu in the top right hand corner of the page (some districts only have one committee: Main Governing Board). If you inspect the HTML for this dropdown, the committee id will be the value in the option element of the div with id="committee-select". 

    meeting_id: str
        String with unique identifier of BoardDoc meeting to scrape.

    Returns
    -------
    str
        Returns text of embedded meeting minutes for BoardDoc meeting if meeting has embedded minutes available.
    """
    data = "id=" + meeting_id + "&" + "current_committee_id=" + committee_id
    minutes_url = "https://go.boarddocs.com/{}/Board.nsf/BD-GetMinutes".format(site)
    response = requests.post(minutes_url, data)
    soup = BeautifulSoup(response.content, "html.parser")
    text = soup.get_text()
    return text
