# Spaced Repetition
Lightweight Spaced Repetition tool for Leetcode review. Track problems you’ve solved and automatically schedule them for future review based on difficulty and recall strength. While designed for LeetCode, the tool is customisable and can be adapted for any spaced-repetition workflow, including flashcards or interview prep.


## Setup
To use the tool, you can either track your solved problems/flashcards locally or on a google spreadsheet. I use the second option for which you will need to install the requirements and setup a spreadsheet and configure your setup. However you can skip this setup entirely and store it locally (requires no setup, you can skip directly to usage). 

### Optional setup to use the tool with Google sheets
- Go to Google Cloud Console → create/select a project → APIs & Services → Library → enable Google Sheets API (and Drive API if needed).
- APIs & Services → Credentials → Create credentials → Service account. Create a service account.
- In the service account page create a JSON key and download it (and store it locally, in the root folder of this project
- Create a Google Sheet in your Drive. Note its Spreadsheet ID (the long id in the sheet URL: https://docs.google.com/spreadsheets/d/<SPREADSHEET_ID>/edit).
- Add details required to leet_config.json


## Usage
To add a new problem to the tracker:
```python
#python spaced_repetition.py add <leetcode-id> <difficulty (scale 1 to 5)>
python spaced_repetition.py add LC-33 3
```

To see what problems are due for review today:
```python
python spaced_repetition.py due
```

To add update for a reviewed problem, to schedule it for next review based on recall quality:
```python
#python spaced_repetition.py review <leetcode-id> <review_quality (scale 1 to 5)>
python spaced_repetition.py review LC-33 4
```
Poorer review quality (<3) will result in a sooner revision. 

To see a summary of everything tracked on the tool so far:
```python
python spaced_repetition.py summary
```
To get a plan for what is coming up:
```python
python spaced_repetition.py plan
```

