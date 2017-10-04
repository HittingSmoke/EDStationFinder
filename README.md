# EDStationFinder

On Sunday I made a thing. On Monday FDev fucked it up.

This script finds two systems which both contain a single station within a certain distance of the main star with a certain size landing pads. The idea was to find optimal passenger routes. Contrary to the insistance of Frontier, passenger missions payouts are lower than or at least equal to pre-2.4. The distance:payout ratio is all out of whack and arguable worse than before they added the distance to station modifier. So this isn't so much use now as it's written.

It could be easily modified to find all sorts of system and station types in proximity to one another.

Yes it's messy. Yes it could be better optimized. It was an afternoon project.

## Installation

I'm not going to hold anyone's hand with this. You're on your own except for some basics.

### Dependencies:
* Python3
* Requests: `pip install requests`
* requests-cache: `pip install requests-cache`

## Usage

Modify the search criteria at the beginning of the file and just run it. It's all automated. It will download data from EDDB and EDSM to perform the searches. Any matches will be written to a file called results.txt in the run directory. The more broad your criteria, the longer it will take to run. It could take anywhere from an hour to a day depending on what you're searching for.
