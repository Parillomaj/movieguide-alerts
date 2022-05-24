import toml
import os
import pyodbc
import inquirer
import requests
import sys
import time
import xml.etree.ElementTree as Et
from tqdm import tqdm
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
import datetime
import pandas as pd
import seaborn as sns


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

        # retrieve external codes
        if self.toml_dict[exhib]['method'] == 'vista':
            for url in self.toml_dict[exhib]['urls']:
                if len(url.split(',')) > 1:
                    payload = {'connectapitoken': url.split(',')[1]}
                    r = requests.get(f'{url.split(",")[0]}/ScheduledFilms', params=payload)
                else:
                    r = requests.get(f'{url}/ScheduledFilms')
                tree = Et.fromstring(r.text)

                for code in tqdm(tree.findall('{http://www.w3.org/2005/Atom}entry'), colour='blue', total=100,
                                 position=0, leave=True):
                    if [code[12][0][1].text, code[12][0][4].text] not in ex_codes:
                        ex_codes.append([code[12][0][1].text, code[12][0][4].text])

        elif self.toml_dict[exhib]['method'] == 'rts':
            for url in self.toml_dict[exhib]['urls']:
                r = requests.get(url)
                tree = Et.fromstring(r.text)

                run_bool = False
                while run_bool is False:
                    if r.status_code == 404 and 'too many' in r.text.lower():
                        for i in range(300, 0, -1):
                            sys.stdout.write(f'\rTrying again in {str(i)} .')
                            sys.stdout.flush()
                            time.sleep(1)
                    else:
                        run_bool = True

                for code in tqdm(tree.findall('filmtitle'), colour='blue', total=100, position=0, leave=True):
                    if [code[10].text, code[0].text] not in ex_codes:
                        ex_codes.append([code[10].text, code[0].text])

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
            in_codes.append([code[0], 'None'])

        # compare to see if any codes are missing; if yes, send an email; if no, pass
        ex_codes.sort(key=lambda x: x[0])
        in_codes.sort(key=lambda x: x[0])

        self.unmatched = [x for x in ex_codes if all(y[0] not in x for y in in_codes)]

        with open(f'{exhib}-Movies.txt', 'w+', encoding='utf-8') as out_file:
            for _code in self.unmatched:
                out_file.write(f'{_code[0]}\t{_code[1]}\n')
        out_file.close()

    def stats(self, exhib):
        today = datetime.datetime.today().strftime('%Y%m%d-%H:%M')
        with open(f'{os.getcwd()}\\stats\\activity.dat', 'a', encoding='utf-8') as stats_file:
            stats_file.write(f'{exhib}-{today}-{len(self.unmatched)}\n')
        stats_file.close()

    @staticmethod
    def analyze():
        data = []
        with open(f'{os.getcwd()}\\stats\\activity.dat', 'r', encoding='utf-8') as activity_file:
            for line in activity_file:
                _date = datetime.datetime.strptime(line.split('-')[1], '%Y%m%d')
                _time = line.split('-')[2]
                exhib = line.split('-')[0]
                num_codes = int(line.split('-')[3])
                data.append([_date, _time, exhib, num_codes])

        df = pd.DataFrame(data, columns=['Date', 'Time', 'Exhib', 'NumCodes']).sort_values('Date')
        x_form = df['Date'].dt.strftime('%A %m-%d').unique()
        plot = sns.lineplot(data=df, x='Date', y='NumCodes', hue='Exhib')
        plot.set_xticklabels(labels=x_form, rotation=30)
        plot.figure.tight_layout()
        plot.savefig(f'{os.getcwd()}\\stats\\time-plot.png')
        activity_file.close()

    def send_message(self, exhib):
        if len(self.unmatched) > 0:
            _from = 'matt.parillo@webedia-group.com'
            to = 'matt.parillo@boxoffice.com,edm@boxoffice.com'
            msg = MIMEMultipart()

            msg['Subject'] = 'ACTION REQUIRED: Missing Movieguide Mappings'
            msg['From'] = _from
            msg['To'] = to
            msg.attach(MIMEText('Missing %s Code(s) from %s; possible mapping / stw needed. File attached.\n\n' %
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

        try:
            _stats = sys.argv[2]
            if _stats.upper() == 'TRUE':
                app.stats(each)
                app.analyze()
        except IndexError:
            choices = ['Yes', 'No']
            question = [inquirer.List('stats', message='run stats analysis?', choices=choices)]
            answer = inquirer.prompt(question)['stats']
            if answer == 'Yes':
                app.stats(each)
                app.analyze()
