# vdeyn_event_scraper
Scrapes the events of vde young net and pushes them to the telegram channel of the vde young net (<a href='https://t.me/vdeyoungnet'>t.me/vdeyoungnet</a>)

    sudo apt-get -y update
    sudo apt-get -y upgrade

install git
    
    sudo apt-get -y git

clone repository
    
    git clone https://github.com/NieThor/vdeyn_event_scraper/

make venv in git folder

    sudo apt-get -y install python3-venv
    cd vdeyn_event_scraper
    python3 venv 

activate venv
    
    source venv/bin/activate
    

install requirements via 

    pip install -r requirements
    
Linux:
download geckodriver

    wget https://github.com/mozilla/geckodriver/releases/download/v0.26.0/geckodriver-v0.26.0-linux64.tar.gz
    
extract tar

    tar -zxvf geckodriver-v0.26.0-linux64.tar.gz

install firefox

    sudo apt-get -y install firefox

start scraper

    python3 "VDE Web Scraper/scraper.py"
