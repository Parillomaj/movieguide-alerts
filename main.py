import toml
import os
import pyodbc
import inquirer
import requests
import sys
import time
import xml
import xml.etree.ElementTree as Et
from tqdm import tqdm
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
import datetime
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt


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
                sources_file.write(f'{_dict}\n')
        sources_file.close()

    def check_data(self, exhib):
        ex_codes = []
        in_codes = []

        # retrieve external codes
        if self.toml_dict[exhib]['method'] == 'vista':
            for url in self.toml_dict[exhib]['urls']:
                try:
                    if len(url.split(',')) > 1:
                        payload = {'connectapitoken': url.split(',')[1]}
                        r = requests.get(f'{url.split(",")[0]}/ScheduledFilms', params=payload, timeout=None,
                                         verify=False)
                        r2 = requests.get(f'{url.split(",")[0]}/Films', params=payload, timeout=None,
                                          verify=False)
                    else:
                        r = requests.get(f'{url}/ScheduledFilms', timeout=None, verify=False)
                        r2 = requests.get(f'{url}/Films', timeout=None, verify=False)

                    tree = Et.fromstring(r.text)
                    tree2 = Et.fromstring(r2.text)

                    for code in tqdm(tree.findall('{http://www.w3.org/2005/Atom}entry'), colour='blue',
                                     position=0, leave=True):
                        try:
                            if [code[12][0][1].text, code[12][0][4].text] not in ex_codes:
                                ex_codes.append([code[12][0][1].text, code[12][0][4].text])
                        except IndexError:
                            if [code[11][0][1].text, code[11][0][4].text] not in ex_codes:
                                ex_codes.append([code[11][0][1].text, code[11][0][4].text])

                    for code in tqdm(tree2.findall('{http://www.w3.org/2005/Atom}entry')):
                        for tag in code:
                            if 'content' in tag.tag:
                                for date in tag[0]:
                                    if 'OpeningDate' in date.tag:
                                        try:
                                            if datetime.datetime.strptime(date.text, '%Y-%m-%dT%H:%M:%S') > \
                                                    datetime.datetime.today():
                                                if [tag[0][0].text, tag[0][3].text] not in ex_codes:
                                                    ex_codes.append([tag[0][0].text, tag[0][3].text])
                                        except ValueError:
                                            pass

                except (requests.exceptions.RequestException, xml.etree.ElementTree.ParseError,
                        ConnectionError) as e:
                    with open(f'{os.getcwd()}\\logs\\errors.txt', 'a+', encoding='utf-8') as error_file:
                        error_file.write(f'{datetime.datetime.now()}\t{exhib}\t{type(e).__name__}\n')

        elif self.toml_dict[exhib]['method'] == 'rts':
            for url in self.toml_dict[exhib]['urls']:
                run_bool = False
                while run_bool is False:
                    try:
                        r = requests.get(url)
                    except (requests.exceptions.RequestException,
                            xml.etree.ElementTree.ParseError) as e:
                        with open(f'{os.getcwd()}\\logs\\errors.txt', 'a+', encoding='utf-8') as error_file:
                            error_file.write(f'{datetime.datetime.now()}\t{exhib}\t{type(e).__name__}\n')
                        run_bool = True
                        continue

                    if r.status_code == 404 and 'too many' in r.text.lower():
                        for i in range(150, 0, -1):
                            sys.stdout.write(f'\rTrying again in {str(i)} .')
                            sys.stdout.flush()
                            time.sleep(1)
                            run_bool = False
                    else:
                        tree = Et.fromstring(r.text)
                        run_bool = True

                        for code in tqdm(tree.findall('filmtitle'), colour='blue', total=len(tree.findall('filmtitle')),
                                         position=0, leave=True):
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

        if len(ex_codes) == 0:
            pass
        else:
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
            with open(f'{os.getcwd()}\\Files\\{exhib}-Movies.txt', 'w+', encoding='utf-8') as out_file:
                for _code in self.unmatched:
                    out_file.write(f'{_code[0]}\t{_code[1]}\n')

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

        df = pd.DataFrame(data, columns=['Date', 'Time', 'Exhib', 'NumCodes']).groupby(['Exhib', 'Date']).sum()
        plot = sns.lineplot(data=df, x='Date', y='NumCodes', hue='Exhib')
        plot.figure.canvas.draw()
        plot.set_xticklabels(labels=plot.get_xticklabels(), rotation=30)
        plot.figure.tight_layout()
        plot.figure.savefig(f'{os.getcwd()}\\stats\\time-plot.png')
        plt.close(plot.figure)
        activity_file.close()

    def send_message(self, exhib):
        _from = 'matt.parillo@webedia-group.com'
        to = 'matt.parillo@boxoffice.com,edm@boxoffice.com'
        msg = MIMEMultipart()
        msg['Subject'] = 'ACTION REQUIRED: Missing Movieguide Mappings'
        msg['From'] = _from
        msg['To'] = to
        if exhib.lower() != 'all':
            if len(self.unmatched) > 0:
                msg.attach(MIMEText('Missing %s Code(s) from %s; possible mapping / stw needed. File attached.\n\n' %
                                    (str(len(self.unmatched)), exhib)))
                with open(f'{os.getcwd()}\\Files\\{exhib}-Movies.txt') as fil:
                    part = MIMEApplication(fil.read())
                    part['Content-Disposition'] = 'attachment; filename="%s"' % f'{exhib}-Movies.txt'
                    msg.attach(part)
                    fil.seek(0)
                    for line in fil:
                        msg.attach(MIMEText(f'{line}'))
                fil.close()
            else:
                pass
        else:
            msg.attach(MIMEText('Missing Code(s); possible mapping / stw needed. File attached.\n\n'))
            with open(f'{os.getcwd()}\\Files\\All\\Movieguide-Movies.txt') as fil:
                part = MIMEApplication(fil.read())
                part['Content-Disposition'] = 'attachment; filename="%s"' % f'Movieguide-Movies.txt'
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

    def send_all(self, exhib, stats: bool):
        # collect data for multiple sources
        try:
            os.remove(f'{os.getcwd()}\\Files\\All\\Movieguide-Movies.txt')
        except FileNotFoundError:
            pass

        for each in exhib:
            self.check_data(each)
            if stats is True:
                self.stats(each)
                self.analyze()
        combined_data = []
        for file in os.listdir(f'{os.getcwd()}\\Files\\'):
            if '.txt' in file.lower():
                if file.split('-')[0].lower() in [x.lower() for x in exhib]:
                    if os.path.getsize(f'{os.getcwd()}\\Files\\{file}') > 0:
                        with open(f'{os.getcwd()}\\Files\\{file}', 'r', encoding='utf-8') as reader:
                            for line in reader:
                                combined_data.append(f'{file.split("-")[0]}\t{line.strip()}\n')
        if len(combined_data) > 0:
            with open(f'{os.getcwd()}\\Files\\All\\Movieguide-Movies.txt', 'w+', encoding='utf-8') as all_movies:
                for movie in combined_data:
                    all_movies.write(movie)

            self.send_message('all')
        else:
            pass


if __name__ == '__main__':
    app = MovieguideAlerts()
    try:
        _exhib = sys.argv[1].split(',')
        _send_all = sys.argv[3]
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
        question2 = [inquirer.List('SendAll', message='combing output?', choices=['true', 'false'])]
        answers2 = inquirer.prompt(question2)
        _send_all = answers2['SendAll']

    if _send_all.lower() == 'false':
        for _each in tqdm(_exhib, leave=True, position=0, colour='Blue'):
            app.check_data(_each)
            try:
                _stats = sys.argv[2]
                if _stats.upper() == 'TRUE':
                    app.stats(_each)
                    app.analyze()
            except IndexError:
                choices = ['Yes', 'No']
                question = [inquirer.List('stats', message='run stats analysis?', choices=choices)]
                answer = inquirer.prompt(question)['stats']
                if answer == 'Yes':
                    app.stats(_each)
                    app.analyze()
    else:
        try:
            _stats = sys.argv[2]
            if _stats.upper() == 'TRUE':
                app.send_all(_exhib, True)
            else:
                app.send_all(_exhib, False)
        except IndexError:
            choices = ['Yes', 'No']
            question = [inquirer.List('stats', message='run stats analysis?', choices=choices)]
            answer = inquirer.prompt(question)['stats']
            if answer == 'Yes':
                app.send_all(_exhib, True)
            else:
                app.send_all(_exhib, False)
