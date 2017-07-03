#!/usr/bin/env python3
import imaplib
import email
import time
import re
import os
import urllib.request
from subprocess import call


file_path = os.path.dirname(os.path.realpath(__file__))


def notify(header, body):
    call(['/usr/bin/notify-send',
          '--expire-time=3',
          '--icon={}/icon.gif'.format(file_path),
          header, body])


def read_credentials(filename='.credentials'):
    contents = (open(file_path + '/' + filename, 'r')
                .read().strip().split('\n'))
    return {
        'server': contents[0],
        'email': contents[1],
        'pass': contents[2]
    }


def connect(credentials):
    mail = imaplib.IMAP4_SSL(credentials['server'])
    mail.login(credentials['email'], credentials['pass'])
    mail.select('inbox')
    return mail


def get_ignored_messages(filename='.ignore'):
    contents = [x for x in
                open(file_path + '/' + filename, 'r').read().split('\n')
                if x]
    return set(map(int, contents))


def ignore_message(index, filename='.ignore'):
    with open(file_path + '/' + filename, 'a') as file:
        file.write('{}\n'.format(index))


def read_all_messages(conn):
    ignored = get_ignored_messages()
    message_texts = dict()
    _, mail_ids = conn.search(None, 'ALL')
    mail_ids = mail_ids[0].split()
    for idx in reversed(mail_ids):
        if int(idx) in ignored:
            continue
        typ, data = conn.fetch(idx, '(RFC822)')
        for response_part in data:
            if isinstance(response_part, tuple):
                msg = email.message_from_string(
                    response_part[1].decode('utf-8'))
                email_subject = msg['subject']
                email_from = msg['from']
                if email_from.lower().startswith('no-reply@arxiv.org'):
                    message_texts[int(idx)] = msg.get_payload()
                time.sleep(3)
    return message_texts


def extract_texts(text_dict):
    splitter = re.compile('[-][-]+\r\n')
    filterer = re.compile(r'\\\\' + '\r\n*')
    return {idx: [x[4:] for x in splitter.split(text_dict[idx])
                  if filterer.match(x)]
            for idx in text_dict}


def parse_text(text):
    try:
        elements = text.split('\r\n\\\\')
        elements[0] = elements[0].split('\r\n')
        title = elements[0][0][6:]
        abstract = elements[1].replace('\r\n', ' ').strip()
        link = elements[2].split(' ')[2]
        return title, abstract, link
    except Exception as ex:
        return None


def fetch_paper_data(conn):
    message_texts = read_all_messages(conn)
    message_texts = extract_texts(message_texts)
    all_data = dict()
    for key in message_texts:
        notify('ArXiv scraper', 'Adding mail {} to task list'.format(key))
        all_texts = message_texts[key]
        all_data[key] = list()
        for text in all_texts:
            val = parse_text(text)
            if val:
                all_data[key].append(val)
    return all_data


def save_papers(data):
    root_path = os.path.expanduser('~/Papers')
    for key in data:
        path = root_path + '/' + str(key)
        mail_data = data[key]
        notify(
            'ArXiv scraper',
            'Downloading mail {} to {}'.format(key, path))
        for name, abstract, abs_link in mail_data:
            paper_path = path + '/' + name
            os.makedirs(paper_path, exist_ok=True)
            with open(paper_path + '/abstract.txt', 'w') as abs_file:
                abs_file.write(abstract)
            filepath = abs_link.replace('/abs/', '/pdf/') + '.pdf'
            urllib.request.urlretrieve(filepath, paper_path + '/paper.pdf')
            # Respect robots.txt
            time.sleep(15)
        notify(
            'ArXiv scraper',
            'Saved mail {} to {}'.format(key, path))
        ignore_message(key)


if __name__ == '__main__':
    notify(
        'ArXiv scraper',
        'Running auto-scraper')
    data = fetch_paper_data(connect(read_credentials()))
    save_papers(data)
    notify(
        'ArXiv scraper',
        'Finished running auto-scraper')
