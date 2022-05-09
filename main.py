import toml
import os
import pyodbc
import inquirer
import requests
import sys
import time
import xml.etree.ElementTree as et
from tqdm import tqdm
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication


class MovieguideAlerts:
    def __init__(self):
        self.unmatched = []
        with open(f'{os.getcwd()}\\config.toml', 'r', encoding='utf-8') as toml_file:
            self.toml_dict = toml.loads(toml_file.read())

        connection = pyodbc.connect("Driver={SQL Server};"
                                    "Server=kraken.csource1.net;"
                                    "Database=master;"
                                    "Trusted_connection=no;"
                                    "UID=readonly;"
                                    "PWD=readonly;")
        self.cursor = connection.cursor()

        with open(f'{os.getcwd()}\\Sources.txt', 'w+', encoding='utf-8') as sources_file:
            for _dict in self.toml_dict.keys():
                sources_file.write(_dict)
        sources_file.close()

    def check_data(self, exhib):
        ex_codes = []
        in_codes = []
        ignore_codes = []

        # retrieve external codes
        if self.toml_dict[exhib]['method'] == 'vista':
            for url in self.toml_dict[exhib]['urls']:
                if len(url.split(',')) > 1:
                    payload = {'connectapitoken': url.split(',')[1]}
                    r = requests.get(f'{url}/ScheduledFilms', params=payload)
                else:
                    r = requests.get(f'{url}/ScheduledFilms')
                tree = et.fromstring(r.text)

                for code in tqdm(tree.findall('{http://www.w3.org/2005/Atom}entry'), colour='blue', total=100,
                                 position=0, leave=True):
                    if [code[12][0][1].text, code[12][0][4].text] not in ex_codes:
                        ex_codes.append([code[12][0][1].text, code[12][0][4].text])

        elif self.toml_dict[exhib]['method'] == 'rts':
            for url in self.toml_dict[exhib]['urls']:
                r = requests.get(url)
        elif self.toml_dict[exhib]['method'] == 'omniterm':
            for url in self.toml_dict[exhib]['urls']:
                r = requests.get(url)
        elif self.toml_dict[exhib]['method'] == 'veezi':
            for url in self.toml_dict[exhib]['urls']:
                r = requests.get(url)
        else:
            sys.stdout.write('Not a valid method.')
            time.sleep(3)
            exit(1)

        # retrieve internal codes
        query = """select * from Cinema..codes
                   where source = '%s'
                """ % exhib
        for code in self.cursor.execute(query).fetchall():
            if code[3] is None:
                in_codes.append([code[2], 'None'])
            else:
                in_codes.append([code[2], code[3]])
        ignore_query = """select code from Cinema..ignore 
                          where source = '%s'
                       """ % exhib
        for code in self.cursor.execute(ignore_query).fetchall():
            ignore_codes.append(code[0])

        # compare to see if any codes are missing; if yes, send an email; if no, pass
        ex_codes.sort()
        in_codes.sort(key=lambda x: x[0])

        compare = [x for x in ex_codes if all(y[0] not in x for y in in_codes)]

        for i, i_code in enumerate(compare):
            if i_code[0] in ignore_codes:
                compare[i].append('ignore')

        for i_code in compare:
            if 'ignore' in i_code:
                pass
            else:
                self.unmatched.append(i_code)

        with open(f'{exhib}-Movies.txt', 'w+', encoding='utf-8') as out_file:
            for _code in self.unmatched:
                out_file.write(f'{_code[0]}\t{_code[1]}\n')
        out_file.close()

    def send_message(self, exhib):
        if len(self.unmatched) > 0:
            _from = 'matt.parillo@webedia-group.com'
            to = 'matt.parillo@boxoffice.com'
            msg = MIMEMultipart()

            msg['Subject'] = 'ACTION REQUIRED: Missing Movieguide Mappings'
            msg['From'] = _from
            msg['To'] = to
            msg.attach(MIMEText('Missing %s Code(s) from %s; possible mapping needed. File attached.\n\n' %
                                (str(len(self.unmatched)), exhib)))
            with open(f'{os.getcwd()}\\{exhib}-Movies.txt') as fil:
                part = MIMEApplication(fil.read())
                part['Content-Disposition'] = 'attachment; filename="%s"' % f'{exhib}-Movies.txt'
                msg.attach(part)
                fil.seek(0)
                for line in fil:
                    msg.attach(MIMEText(f'{line}'))
            fil.close()

            s = smtplib.SMTP('smtp.gmail.com', 587)
            s.starttls()
            s.ehlo()
            s.login('matt.parillo@webedia-group.com', 'ccgvmrhwltnbgqem')
            s.sendmail(_from, to.split(','), msg.as_string())
            s.quit()
        else:
            pass


if __name__ == '__main__':
    app = MovieguideAlerts()
    try:
        _exhib = sys.argv[1].split(',')
    except IndexError:
        choices = []
        with open(f'{os.getcwd()}\\Sources.txt', 'r', encoding='utf-8') as _file:
            for _line in _file:
                choices.append(_line.strip())
        _file.close()
        choices.sort()
        questions = [inquirer.Checkbox('imports', message='check which import?', choices=choices)]
        answers = inquirer.prompt(questions)
        _exhib = answers['imports']

    for each in _exhib:
        app.check_data(each)
        app.send_message(each)
