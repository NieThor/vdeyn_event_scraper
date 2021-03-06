import requests
import json
from bs4 import BeautifulSoup
import datetime
import time
import platform
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.firefox.options import Options
import telethon
import logging
import pathlib
PATH = pathlib.Path(__file__).parent.absolute()

datetime_format = '%d.%m.%Y %H:%M'
date_format = '%d.%m.%Y'

base_url = 'https://www.vde.com/de/vde-youngnet/veranstaltungen'

# read api information from json file
with open(f'{PATH}\\api_infos.json', 'rb') as api_codes:
    api_json = json.load(api_codes)
    api_id = int(api_json['api_id'])
    api_hash = api_json['api_hash']
logging.INFO = True
client = telethon.TelegramClient('SVDEE', api_id, api_hash)


class VdeEvent:
    """
    class that represents an event from the vde young net
    """

    def __init__(self):
        self.title = None
        self.start = None
        self.end = None
        self.location = None
        self.description = None
        self.img_url = None
        self.event_url = None
        self.last_posting_time = None
        self.language = None


def datetime_dict_to_str(dt_dict):
    return {key: dt_dict[key].strftime(datetime_format) for key in dt_dict.keys()}


def strip_time(time_str_list):
    """
    Strips time from date or datetime string
    datetime_format = '%d.%m.%Y %H:%M'
    date_format = '%d.%m.%Y'
    :param time_str_list: list of time_strings/ one time_string is allowed as well
    :return: time_list: list of times in datetime
    """

    if not type(time_str_list) is list:
        time_str_list = [time_str_list]
    time_list = []
    for time_str in time_str_list:
        if ':' in time_str:  # colon means datetime
            time_str = time_str[:time_str.index(':') + 3]
            time_list.append(datetime.datetime.strptime(time_str, datetime_format))
        else:  # everything else is a date
            time_str = time_str[:time_str.index('.') + 8]
            time_list.append(datetime.datetime.strptime(time_str, date_format))
    return time_list


try:
    with open('last_scraping_time.json', 'rb') as time_read:
        curr_last_times = json.load(time_read)

    curr_last_times = {key: strip_time(curr_last_times[key])[0] for key in curr_last_times.keys()}
except FileNotFoundError:
    curr_last_times = {}


def prettify_string(string: str):
    """
    Prettifies string
        - Gets rid of unnessarcy characters, leading whitespaces...

    :param string: to prettify
    :return: prettified string
    """
    lines = string.split('\n')
    for i in range(len(lines) - 1, -1, -1):
        lines[i] = lines[i].strip()
        if lines[i] == '' or lines[i] == '\r':  # remove empty lines
            lines.pop(i)
    return '\n'.join(lines)


def prettify_string_with_list(tag):
    bullet = '\u2022'
    unordered_lists = tag.find_all('ul')
    ordered_lists = tag.find_all('ol')
    for u_list in unordered_lists:
        for li in u_list.find_all('li'):
            li.string.replace_with(' ' + bullet + f' {li.string}')

    for o_list in ordered_lists:
        for i, li in enumerate(o_list.find_all('li')):
            li.string.replace_with(' ' + str(i+1) + f'. {li.string}')

    return prettify_string(tag.get_text())


async def scrape_events(driver):
    """
    Scrapes events from VDE Young Net webpage

    :param driver: selenium webdriver to use
    :return:
    """

    global curr_last_times
    channel = await client.get_entity('@TN_freqtrade_14052020_bot')#t.me/vdeyoungnet')  # getting the telegram channel
    events = {}
    i = 0
    while True:
        if i != 0:
            time.sleep(60 * 60)  # update every hour
        i += 1
        curr_hour = datetime.datetime.now().hour
        if 21 < curr_hour or curr_hour < 9:  # no messages between 21:00 and 9:00
            continue
        try:
            driver.get(base_url)
            wait = WebDriverWait(driver, 10)

            # wait until events are lazy-loaded
            wait.until(EC.presence_of_element_located((By.CLASS_NAME, 'ci-teaser-automatic')))

            # first three events are teasers
            events_raw = driver.find_elements_by_class_name('ci-teaser-automatic')[0:3]

            # others are available in the search-list
            events_raw += driver.find_elements_by_class_name('ci-search-teaser')

            # only posting if event is in less than 4 weeks?
            curr_time_w_offset = datetime.datetime.now() + datetime.timedelta(days=40)

            # only posting maximum every week
            # posting_offset = datetime.datetime.now() - datetime.timedelta(days=7)

            for event_raw in events_raw:
                event_url = event_raw.find_element_by_tag_name('a').get_attribute('href')
                if event_url not in events.keys():
                    event = VdeEvent()
                    event.event_url = event_url
                else:
                    event = events[event_url]
                resp = requests.get(event_url)
                soup = BeautifulSoup(resp.text, 'html.parser')
                if 'vde.com' in event_url:  # some events are hosted on vde.com

                    # getting event information from the html code considering classes and content
                    event.title = prettify_string(soup.find('h1', {'class': 'ci-h2'}).get_text())
                    event.img_url = 'https://www.vde.com' + \
                                    soup.find('div', {'class': 'ci-image-caption'}).find('img')['srcset']

                    table = soup.find('table', {'class': 'ci-stencil-event-table'})
                    tbody = table.find('tbody')
                    if None is tbody:
                        tbody = table
                    rows = tbody.find_all('tr')
                    temp_tds = rows[0].find_all('td')
                    temp_start = temp_tds[1].get_text()
                    if len(temp_tds) > 2:
                        temp_start += f' {temp_tds[2].get_text()}'
                    event.start = strip_time(temp_start)
                    temp_tds = rows[1].find_all('td')
                    temp_end = temp_tds[1].get_text()
                    if len(temp_tds) > 2:
                        temp_end += f' {temp_tds[2].get_text()}'
                    event.end = strip_time(temp_end)

                    def find_by_str(tag, search_str):
                        return tag.name == 'div' and tag.has_attr('class') and 'row-1' in tag[
                            'class'] and search_str in tag.get_text()

                    def find_location(tag):
                        return find_by_str(tag, 'Veranstaltungsort')
                    event.location = [prettify_string(
                        soup.find(find_location).parent.find_all('div')[1].find('p').get_text())]

                    def find_language(tag):
                        return find_by_str(tag, 'Veranstaltungs-Sprache')

                    def find_desc(tag):
                        return find_by_str(tag, 'Beschreibung')

                    def find_desc_2(tag):
                        return find_by_str(tag, 'Bemerkung')

                    event.language = [soup.find(find_language).parent.find('img').get('title')]

                    desc = soup.find(find_desc)
                    if None is desc:
                        desc = soup.find(find_desc_2)
                    if None is not desc:
                        event.description = prettify_string_with_list(desc.parent.find_all('div')[1])

                elif 'vde-verlag.de' in event_url:  # some events are hosted on vde-verlag.de

                    # getting event information from the html code considering classes and content
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
                if event.event_url in curr_last_times:
                    continue
                # only post event if not been posted recently and event is coming up soon
                if (None is event.last_posting_time) and event.start[0] <= curr_time_w_offset:  # or event.last_posting_time < posting_offset) \
                    message = f'[{event.title}]({event_url})\n'
                    for i in range(len(event.start)):
                        if len(event.start) > 1:
                            message += f'{i + 1}. Termin\n'
                        message += f'Beginn: {event.start[i].strftime(datetime_format) + " Uhr" if type(event.start[i]) is datetime.datetime else event.start[i].strftime(date_format)}\n'
                        if (type(event.start[i]) is datetime.date
                            and type(event.end[i]) is datetime.date
                            and event.start[i] != event.end[i]) \
                                or (type(event.start[i]) is datetime.datetime
                                    and type(event.end[i]) is datetime.date
                                    and event.start[i].date() != event.end[i]):
                            message += f'Ende: {event.end[i].strftime(datetime_format if type(event.end[i]) is datetime.datetime else date_format)}\n'
                        if len(event.language) != 0:
                            message += 'Sprache: '
                            if 'de' in event.language[0]:
                                message += "\U0001f1e9\U0001f1ea"
                            else:
                                message += "\U0001f1ec\U0001f1e7"
                            message += '\n'
                        event.location[i] = event.location[i].replace('\n', ', ')
                        message += f'Ort: {event.location[i]}\n\n'
                    if None is not event.description:
                        message += f'__Beschreibung:__\n{event.description}'
                    image = requests.get(event.img_url, stream=True).content
                    with open('temp_image', 'wb') as img_file:
                        img_file.write(image)
                    with open('temp_image', 'rb') as img_file:
                        pass
                        await client.send_message(entity=channel, message=f'[{event.title}]({event.event_url})\n',
                                                  file=img_file)

                    await client.send_message(entity=channel, message=message,
                                              link_preview=True)  # , file=img_file) not usable right now, because text is limited elsewise
                    event.last_posting_time = datetime.datetime.now()
                    curr_last_times[event.event_url] = event.last_posting_time
                    with open('last_scraping_time.json', 'w') as time_write:
                        json.dump(datetime_dict_to_str(curr_last_times), time_write)

                events[event.event_url] = event  # update or append event
        except Exception as e:
            with open('log.txt', 'a+') as log_file:
                log_file.write(f'{datetime.datetime.now().strftime(datetime_format)}: {str(e)}\n')


if __name__ == '__main__':
    options = Options()
    options.headless = True
    gecko_path = f'{PATH}\\{"geckodriver" if platform.system() == "Linux" else "geckodriver.exe"}'
    web_driver = webdriver.Firefox(options=options,
                                   executable_path=gecko_path)
    with client:
        client.loop.run_until_complete(scrape_events(web_driver))
    web_driver.quit()
