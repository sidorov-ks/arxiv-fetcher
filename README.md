# arxiv-fetcher
A small tool for scraping arXiv papers from email feed.

## How to use
1. Create two files in the same directory with the script:

- `.ignore` - leave it empty;
- `.credentials` - write there three lines (your email server - `imap.yandex.com`, your email address and your password).

2. Run the script - or, better yet, create a cron job: `export DISPLAY=:0.0 && export XAUTHORITY=/home/<username>/.Xauthority && sudo -u pretorium /usr/bin/python3 /home/<username>/Repos/ArxivFetcher/fetcher.py &> /tmp/cron.log`

That's it! Now the script will crawl your inbox, fetch all emails from arXiv and save all abstracts and pdf's in `~/Papers`.
