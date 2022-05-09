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
            for dict in self.toml_dict.keys():
                sources_file.write(dict)
        sources_file.close()

    def check_data(self, exhib):
        ex_codes = []
        in_codes = []

        # retrieve external codes
        if self.toml_dict[exhib]['method'] == 'vista':
            for url in self.toml_dict[exhib]['urls']:
                r = requests.get(f'{url}/Films')
                tree = et.fromstring(r.text)

                for code in tqdm(tree.findall('{http://www.w3.org/2005/Atom}entry'), colour='blue', total=100,
                                 position=0):
                    ex_codes.append([code[7][0][0].text, code[7][0][3]])

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
            in_codes.append([code[2], code[3]])

        # compare to see if any codes are missing; if yes, send an email; if no, pass
        ex_codes.sort()
        in_codes.sort(key=lambda x: x[0])

        for out_code in ex_codes:
            if out_code in in_codes:
                pass
            else:
                self.unmatched.append(out_code)

        with open(f'{exhib}-Movies.txt', 'w+', encoding='utf-8') as out_file:
            for _code in self.unmatched:
                for out_code in ex_codes:
                    if _code == out_code[0]:
                        out_file.write(f'{out_code[0]}\t{out_code[1]}')
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
            for line in _file:
                choices.append(line.strip())
        _file.close()
        choices.sort()
        questions = [inquirer.Checkbox('imports', message='check which import?', choices=choices)]
        answers = inquirer.prompt(questions)
        _exhib = answers['imports']

    for each in _exhib:
        app.check_data(each)
        app.send_message(each)
