## MovieGuide Alerts
### Abstract
The movieguide alerts system is designed to catch missing movieguide 
mappings that may prevent metadata from populating on both our apps
and our Boost ticketing pages

### Configuration
A .toml file is used to set configuration parameters needed for the
program to operate. The following critical dictionary keys should be
added:

    [exhibitor_name]
    urls = ['list','of','strings']
    prefix = 'alt_id prefix as string'
    chain_id = int
    filter_houses = 's,t,r'
    search_on = 'str'
    method = 'str'

The exhibitor name (dictionary key) should always be set to the codes
source in Foxpro.

if there is no chain_id for the location (unlikely) it should be set
to **0**; *a chain_id as int is a required parameter, so do not
leave blank*.

filter_houses should be passed in as a comma separated list of
strings, **not** an array.  These houses will be skipped.

search_on needs to be specific strings; the program will accept:
- `chain` -- the chain_id will be used 
- `alt` -- the prefix will be used 
- `name` -- the exhibitor_name will be used

This parameter determines how the program will search theater-based
data within our API.  The program will default to "chain"

method is also a specific list of strings; the program will accept:
- `vista` -- the query pattern will assume a vista endpoint
- `rts` -- the query pattern will assume an rts endpoint
- `omniterm` -- the query pattern will assume an omniterm endpoint
- `veezi` -- the query pattern will assume a veezi endpoint
- `fandango` -- special custom logic for Fandango codes handling
- `amc` -- special custom logic for MTXAMC codes source

### Execution
The program has a built-in multi-select CLI which allows the user to run
the script manually at any time. The script can also be executed by passing
the required arguments into the CMD prompt:
    
    python main.py [arg1] [arg2]

- **arg1**: The source(s) to be checked, as a comma delimited list. Source
    names should be an exact match to their corresponding toml entry.
- **arg2**: Should be `TRUE` or `FALSE`, indicating whether the 
    analysis should be run along with the program.

Currently, the program is executed primarily via multiple .bat files scheduled
via Windows Task Scheduler.  The root directory can be found here:
`S:\\Mtxcrawler\\Gathertimes\\MovieguideAlerts\\Control\\`