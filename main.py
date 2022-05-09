import toml
import os
import pyodbc
import inquirer
import requests
import sys
import time
import xml.etree.ElementTree as et
from tqdm import tqdm


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
                    ex_codes.append(code[12][0][1])

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


if __name__ == '__main__':
    app = MovieguideAlerts()
    try:
        exhib = sys.argv[1]
    except IndexError:
        choices = []
        with open(f'{os.getcwd()}\\Sources.txt', 'r', encoding='utf-8') as _file:
            for line in _file:
                choices.append(line.strip())
        _file.close()
        choices.sort()
        questions = [inquirer.Checkbox('imports', message='check which import?', choices=choices)]
        answers = inquirer.prompt(questions)
        exhib = answers['imports']

    for each in exhib:
        app.check_data(each)
