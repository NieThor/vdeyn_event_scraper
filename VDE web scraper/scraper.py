import asyncio

import urllib.request as urllib
import requests
import json
import sys
from bs4 import BeautifulSoup
import datetime
import re
import os
import time

datetime_format = '%d.%m.%Y %H:%M'
date_format = '%d.%m.%Y'

base_url = 'https://www.vde.com/de/vde-youngnet/veranstaltungen'
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.firefox.options import Options
import telethon
import logging

with open('api_infos.json', 'rb') as api_codes:
    api_json = json.load(api_codes)
    api_id = int(api_json['api_id'])
    api_hash = api_json['api_hash']
logging.INFO = True
client = telethon.TelegramClient('SVDEE', api_id, api_hash)


class VdeEvent:

    def __init__(self):
        self.title = None
        self.start = None
        self.end = None
        self.location = None
        self.description = None
        self.img_url = None


def strip_time(time_str_list):
    if not type(time_str_list) is list:
        time_str_list = [time_str_list]
    time_list = []
    for time_str in time_str_list:
        if ':' in time_str:
            time_str = time_str[:time_str.index(':') + 3]
            time_list.append(datetime.datetime.strptime(time_str, datetime_format))
        else:
            time_str = time_str[:time_str.index('.') + 8]
            time_list.append(datetime.datetime.strptime(time_str, date_format))
    return time_list


def prettify_string(string: str):
    lines = string.split('\n')
    for i in range(len(lines) - 1, -1, -1):
        lines[i] = lines[i].strip()
        if lines[i] == '' or lines[i] == '\r':
            lines.pop(i)
    return '\n'.join(lines)


async def scrape_events(driver):
    channel = await client.get_entity('t.me/vdeyoungnet')
    while True:
        driver.get(base_url)
        wait = WebDriverWait(driver, 10)
        wait.until(EC.presence_of_element_located((By.CLASS_NAME, 'ci-teaser-automatic')))
        events_raw = driver.find_elements_by_class_name('ci-teaser-automatic')[0:3]
        events_raw += driver.find_elements_by_class_name('ci-search-teaser')
        curr_time_w_offset = datetime.datetime.now() + datetime.timedelta(days=40)
        events = []
        for event_raw in events_raw:
            event = VdeEvent()
            event_url = event_raw.find_element_by_tag_name('a').get_attribute('href')
            resp = requests.get(event_url)
            soup = BeautifulSoup(resp.text, 'html.parser')
            if 'vde.com' in event_url:
                event.title = prettify_string(soup.find('h1', {'class': 'ci-h2'}).get_text())
                event.img_url = 'https://www.vde.com' + \
                                                  soup.find('div', {'class': 'ci-image-caption'}).find('img')['srcset']

                table = soup.find('table', {'class': 'ci-stencil-event-table'})
                tbody = table.find('tbody')
                if None is tbody:
                    tbody = table
                rows = tbody.find_all('tr')
                event.start = strip_time(rows[0].find_all('td')[1].get_text())
                event.end = strip_time(rows[1].find_all('td')[1].get_text())

                def find_location(tag):
                    return tag.name == 'div' and tag.has_attr('class') and 'row-1' in tag[
                        'class'] and 'Veranstaltungsort' in tag.get_text()

                event.location = [prettify_string(
                    soup.find(find_location).parent.find_all('div')[1].find('p').get_text())]

                def find_desc(tag):
                    return tag.name == 'div' and tag.has_attr('class') and 'row-1' in tag[
                        'class'] and 'Beschreibung' in tag.get_text()

                def find_desc_2(tag):
                    return tag.name == 'div' and tag.has_attr('class') and 'row-1' in tag[
                        'class'] and 'Bemerkung' in tag.get_text()

                desc = soup.find(find_desc)
                if None is desc:
                    desc = soup.find(find_desc_2)
                event.description = prettify_string(desc.parent.find_all('div')[1].get_text())
            elif 'vde-verlag.de' in event_url:
                event.title = prettify_string(soup.find('h1', {'class': 'hyphenate'}).get_text())
                event.img_url = 'https://www.vde-verlage.de' + \
                                                  soup.find('img', {'id': 'cover'})['src']
                starts = []
                ends = []
                locations = []
                table = soup.find('table', {'id': 'seminartermine'})
                rows = table.find('tbody').find_all('tr')
                for row in rows:
                    start_col, end_col, loc_col = row.find_all('td')[1:4]
                    starts.append(start_col.get_text())
                    ends.append(end_col.get_text())
                    locations.append(loc_col.find('span', {'class': 'hidden-xs'}).get_text())

                event.start = strip_time(starts)
                event.end = strip_time(ends)
                event.location = locations
                event.description = prettify_string(
                    soup.find('div', {'id': 'beschreibung'}).get_text())

            if event.start[0] <= curr_time_w_offset:
                message = f'[{event.title}]({event_url})\n'
                for i in range(len(event.start)):
                    if len(event.start) > 1:
                        message += f'{i+1}. Termin\n'
                    message += f'Beginn: {event.start[i].strftime(datetime_format if type(event.start[i]) is datetime.datetime else date_format)}\n'
                    if (type(event.start[i]) is datetime.date
                        and type(event.end[i]) is datetime.date
                        and event.start[i] != event.end[i]) \
                            or (type(event.start[i]) is datetime.datetime
                                and type(event.end[i]) is datetime.date
                                and event.start[i].date() != event.end[i]):
                        message += f'Ende: {event.end[i].strftime(datetime_format if type(event.end[i]) is datetime.datetime else date_format)}\n'
                    message += f'Ort: {event.location[i]}\n\n'
                message += f'__Beschreibung:__\n{event.description}'
                image = requests.get(event.img_url, stream=True).content
                with open('temp_image', 'wb') as img_file:
                    img_file.write(image)
                with open('temp_image', 'rb') as img_file:
                    await client.send_message(entity=channel, message=f'[{event.title}]({event_url})\n', file=img_file)

                await client.send_message(entity=channel, message=message, link_preview=True)#, file=img_file)
            events.append(event)
            break

        time.sleep(60 * 60 * 12)  # update all 12 hours


if __name__ == '__main__':
    options = Options()
    options.headless = True
    driver = webdriver.Firefox(options=options, executable_path=r'geckodriver.exe')
    with client:
        client.loop.run_until_complete(scrape_events(driver))
    driver.quit()
