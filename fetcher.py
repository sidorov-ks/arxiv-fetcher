#!/usr/bin/env python3
import imaplib
import email
import time
import re
import os
import urllib.request
from chardet import UniversalDetector
from subprocess import call


file_path = os.path.dirname(os.path.realpath(__file__))


def _(rel_path):
    return '{}/{}'.format(file_path, rel_path)


def notify(body, urgency='normal'):
    print(body)
    call(['notify-send',
          '--expire-time=3',
          '--icon={}/icon.gif'.format(file_path),
          '-u', urgency,
          'Arxiv mail scraper', body])


def is_running(pid):
    try:
        os.kill(pid, 0)
    except OSError:
        return None
    else:
        return pid


def write_lock(path_to_pidfile):
    if os.path.exists(path_to_pidfile):
        pid = int(open(path_to_pidfile).read())

        if is_running(pid):
            raise SystemExit
        else:
            os.remove(path_to_pidfile)

        open(path_to_pidfile, 'w').write(str(os.getpid()))
        return path_to_pidfile


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
                open(_(filename), 'r').read().split('\n')
                if x]
    return set(map(int, contents))


def ignore_message(index, filename='.ignore'):
    with open(_(filename), 'a') as file:
        file.write('\n{}'.format(index))


def read_all_messages(conn):
    ignored = get_ignored_messages()
    message_texts, subjects = dict(), dict()
    _, mail_uids = conn.uid('search', None, 'ALL')
    mail_uids = mail_uids[0].split()
    for idx in reversed(mail_uids):
        if int(idx) in ignored:
            continue
        typ, data = conn.uid('fetch', idx, '(RFC822)')
        for response_part in data:
            if isinstance(response_part, tuple):
                try:
                    detector = UniversalDetector()
                    raw_msg = response_part[1]

                    detector.feed(raw_msg)
                    detector.close()

                    msg = email.message_from_string(
                        raw_msg.decode(detector.result['encoding']))
                except:
                    notify(
                        'Failed to read email with uid={}'.format(idx),
                        urgency='critical'
                    )
                email_subject = msg['subject']
                email_from = msg['from']
                if email_from.lower().startswith('no-reply@arxiv.org'):
                    message_texts[int(idx)] = msg.get_payload()
                    subjects[int(idx)] = email_subject
                else:
                    ignore_message(int(idx))
                time.sleep(3)
    return message_texts, subjects


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
    message_texts, subjects = read_all_messages(conn)
    message_texts = extract_texts(message_texts)
    all_data = dict()
    uids = list()
    for key in message_texts:
        all_texts = message_texts[key]
        all_data[key] = list()
        for text in all_texts:
            val = parse_text(text)
            if val:
                all_data[key].append(val)
        all_data[key] = (subjects[key], all_data[key])
        uids.append(str(key))

    if uids:
        notify(
            'Adding mails with uids {} to task list'.format(
                ', '.join(uids)
            )
        )
    return all_data


def save_papers(data):
    root_path = os.path.expanduser('~/Papers')
    for key in data:
        subj, mail_data = data[key]
        path = root_path + '/' + str(key) + ' ({})'.format(subj)
        notify(
            'Downloading mail with uid={} to {}'.format(key, path)
        )
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
            'Saved mail with uid={} to {}'.format(key, path)
        )
        ignore_message(key)


if __name__ == '__main__':
    write_lock('/tmp/arxiv-mail-reader.lock')
    try:
        notify(
            'Running auto-scraper'
        )
        data = fetch_paper_data(connect(read_credentials()))
        save_papers(data)
        notify(
            'Finished running auto-scraper'
        )
    except Exception as ex:
        notify(
            ('An unknown error occurred while running scraper. ' +
             'See logfile for more details.'),
            urgency='critical'
        )
        raise ex
