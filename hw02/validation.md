# 1C- Errors
## Error #1
### Explanation
Ran the code pasted below and waited 5 minutes and nothing happened. I asked Claude what I should do and it said to press ctrl c and see if any errors appeared. None did so Claude tolde me to save the hw02_eda.py and try running the code again.

(.venv) PS C:\MIS3060\mis3060-bi-ai-1> python hw02/hw02_eda.py
>> ^C
## Error #2
### Explanation
After saving the hw02_eda.py I typed the code pasted below and recieved the error that followed. I pasted this into Claude, and relized that it was just a small mistake of not including hw02\ before the file.

(.venv) PS C:\MIS3060\mis3060-bi-ai-1> python hw02_eda.py
C:\MIS3060\mis3060-bi-ai-1\.venv\Scripts\python.exe: can't open file 'C:\\MIS3060\\mis3060-bi-ai-1\\hw02_eda.py': [Errno 2] No such file or directory
## Conclusion 
After fixing both of these problems the code ran smoothly with no errors! 
# 2A- Known-Answer Benchmarks
| Check | Expected | Your Script Produced | Match? | Notes |
|---|---|---|---|---|
| Dataset shape | (298772, 9) |(298772, 9) | Yes | |
| Null count — `security_id` | 101,597 | 101,597 | Yes | |
| Null count — `amount` | 0 | 0 | Yes | |
| Unique `txn_type` values | 6 | 6 | Yes | |
| Count of `Buy` transactions | 83,556 | 83,556 | Yes | |
| `txn_date` data type | object | datetime64[us] | No | Claude Conversation: "The `txn_date` data type that our code gave me (datetime64[us]) does not equal the expected type (Object) why is that? Just tell me what was went wrong do not change anything in my file."  The discrepancy: "Script converts txn_date to datetime before step 3 runs, so it reports datetime64 instead of the raw CSV type (object)." |
| Earliest `txn_date` | 2020-01-01 | 2020-01-01 | Yes | |
| Latest `txn_date` | 2024-12-30 | 2024-12-30 | Yes | |
| Duplicate `txn_id` count | 0 | 0 | Yes | |
| Mean `amount` | $54,075.17 | $54,075.17 | Yes | |
| Median `amount` | $41,220.48 | $41,220.49 | No | Claude Conversation: "The Median amount that our code gave me ($41,220.49) does not equal the expected amount($41,220.48) why is that? Just tell me what was went wrong do not change anything in my file." The discrepancy: "True median is $41,220.485 (average of the two middle values). The one-cent difference is rounding, not a calculation error."|
| Skewness of `amount` | 1.15 | 1.15 | Yes | |
| Correlation `shares`–`amount` | 0.65 | 0.65  | Yes | |
| Correlation `price`–`amount` | 0.64 | 0.64 | Yes | |
| Correlation `shares`–`price` | 0.00 | 0.00 | Yes | |
| Negative `shares` count (Buy only) | 836 | 836 | Yes | |
| Profile file created | Yes | Yes | Yes | |
| Chart files created (3) | Yes | Yes | Yes | |
## 2B — Explain the Code and Output

#### 1. Did Claude's predicted outputs (from Prompt 1) match what you actually saw in the terminal? List any discrepancies.
Claude did not supply literal numbers in Prompt 1, since it only had the script and not the data. So instead of fabricating numbers, it stated explicitly what form each value would take. With that, Claude did predict most of the outputs correctly. It correctly predicted the shape (298,772 × 9) because that number is already coded/included in the script as EXPECTED_SHAPE, and although it did not give exact numerical solutions, it did correctly predict the general structure of each section. Two errors that I did observe were that Claude's prediction used the standard datetime64[ns] and object labels for txn_date and txn_type, but the actual output showed datetime64[us] and str.

#### 2. What did Claude flag as potentially unexpected or worth investigating (from Prompt 2)?
Claude flagged 6 things worth investigating:

1. "836 Buy rows have negative shares (about 1% of buys, as low as −499.63)"
2. "Advisory fees are heavily skewed (mean $7,375 vs. median $859)."
3. Dividend amounts look like full trade values. A dividend averaging $64K with shares × price math means the whole position value is being recorded, not a dividend payment (usually a few percent of that value).
4. "Amount has no sign. Withdrawals and sells are positive, just like deposits and buys. If you calculate net flows or cash balances, you have to apply the sign based on txn_type. A plain sum() will overstate them."
5. "Client IDs go up to 3,192, but there are only 2,700 unique clients."
6. "The dataset ends December 30, 2024, not December 31."

#### 3. Did Claude mention the 101,597 null values in security_id? What explanation did it give?
Yes, Claude stated that there are exactly this many missing values in not only security_id but also shares and price. But this is not an error or something to be concerned about because Deposit (35,981) + Withdrawal (29,850) + Advisory Fee (35,766) = 101,597. It stated that these are only cash transactions and stocks are not involved, so these data points being blank is expected.

#### 4. Did Claude flag the txn_date column as a concern? Why would that matter for a time-series analysis?
No, Claude did not flag this column as a concern because the Python script that Claude created for me already switched the data type to datetime64[us] to avoid any problems with the dataset. This would matter for a time-series analysis because: "you couldn't do date math like computing days between transactions, sort transactions chronologically (text sorts alphabetically, not by date), or group by month or year, since none of those operations work correctly on plain strings." (quoted section used AI for help, see question 6 below)

#### 5. Open your three chart files. Does what you see in each image match Claude's explanation of that section of the output? Note any differences.
1. Histogram: 
"Histogram of amount: 100 bins, with a red dashed line at the mean and a green line at the median."
This discription does match the graph as bins does = 100, and the chart shows the red dashed mean line at about 55,000 and green median line at about 40,000
2. Box plot: 
"Horizontal box plot: one box per txn_type, in the same order as section 11. The try/except handles old and new matplotlib versions. On matplotlib 3.9 you may see a harmless MatplotlibDeprecationWarning from the fallback."
ALthough thechnically the same they will look a little different because the order of section 11 is the opisite of the order of the box chart so they are just flipped. Also there is no warning or anything about MatplotlibDeprecation. 
3. Scatter plot:
"Scatter of shares vs. amount: one color per transaction type, with small, semi-transparent dots because there are about 300k points."
The is a correct description of the scatter plot graph as there is one color per transaction type, transparent dots that get more opaque, and there are about 300,000 pts. 
#### 6. Paste one follow-up question you asked Claude, and Claude's answer.
Question:

Why could the txt_data colum be a concern? and how would it negativly effect a time-series analysis? 
The core issue: a computer treats text and dates completely differently.

Answer:

Sorting breaks. When txn_date is stored as text, "sorting" it means comparing the characters one at a time, like alphabetizing a word. As long as every date is formatted consistently as YYYY-MM-DD, that actually happens to sort correctly by coincidence, since the year always comes first, then month, then day. But if the format is ever inconsistent, say some rows use 1/5/2024 and others use 2024-01-05, alphabetical sorting no longer lines up with chronological order at all. You could easily miss this until it's already thrown off a report.

Subtraction doesn't exist for text. This is the bigger issue, and it's the one the assignment's question about "average days between transactions" is really pointing at. Dates stored as actual date objects support subtraction: date2 - date1 gives you back a span of time, like "14 days." Text strings don't support that operation at all. "2024-01-15" - "2024-01-01" isn't something Python can compute; it would just throw an error. So Claude Cowork would have to convert the column to a real date type first, as a separate step, before it could compute anything like days-between or a rolling monthly total. If that conversion step were skipped or done wrong, the whole calculation would fail or, worse, silently produce nonsense.

Grouping by month or year gets harder. With a real date type, you can pull out "just the month" or "just the year" directly. With text, you'd have to manually chop up the string, which is fragile and breaks if the format ever varies.
## 2C- Business Check & Cross-Validation
1. security_id, shares, and price are all null in exactly 101,597 rows. Looking at the txn_type value counts, which three transaction types would you expect to have no security — and why? Do the counts add up to 101,597?

As previously discussed in part 2B: Deposit (35,981) + Withdrawal (29,850) + Advisory Fee (35,766) = 101,597, which matches exactly the 101,597 null values in each of security_id, shares, and price. This is because they are cash transactions and not stock transactions, and will not have or require a security.

2. There are 83,556 Buy transactions and 59,755 Sell transactions. What does it mean for a wealth management firm to have significantly more Buys than Sells over a five-year period?

This can mean many things. It can imply that a wealth management firm is receiving more assets from their clients to invest, and if they are receiving this money, it could also mean their clientele is more risk tolerant and is ok with their money entering the stock market. Finally, it could mean that the managers could be moving capital around from bonds or other fixed income into the market.

3. The txn_date column is stored as a string (type object) rather than a date. If Claude Cowork generated code to compute the average number of days between transactions, what would go wrong if the dates remained as strings?

If dates remained as a string, this could cause a lot of problems because Python would just read this as text, and you cannot subtract text or compute any numerical outputs. This would ultimately result in an error or give an incorrect solution.

4. Wildcat Capital has 2,700 clients served by 25 advisors. Is that ratio — roughly 108 clients per advisor — plausible for a registered investment advisory firm?

This is very plausible because, "Based on data from the Investment Adviser Association and FINRA, the average securities-registered advisor serves approximately 173 clients," and the number 108 is well within a normal margin. The only thing that does concern me is there are 3,192 clients, it's just that 2,700 of them made transactions, so it could be 128 clients, which is higher but still in range.
https://smartasset.com/advisor-resources/average-number-of-clients-per-financial-advisor 

5. 836 Buy transactions have negative shares values (as low as −499.63), while every other transaction type in the dataset has only positive share values. What are two plausible business explanations for a negative share count on a Buy transaction (for example, a data-entry sign error versus a legitimate correction or reversal entry), and what would you do next to determine which explanation is more likely?

I believe the two plausible business explanations are a data-entry sign error or a reversal entry. To determine which explanation is more likely, I would prompt Claude to go back through the data and see whether the exact same number was previously recorded as a positive value and that it has the same client ID. If it was, then the negative value could represent a reversal entry. If these duplicates were present, I would have Claude clean the data by canceling out those matching entries. Then, if there were still negative values remaining, I would change those to positive values because they would most likely be sign errors.

6. What did each script return?

Script A:

 Rows where txn_type == 'Buy': 83,556

Script B:

 Total rows:                         298,772
Rows that are Sell, Deposit, Withdrawal, Dividend, or Advisory Fee: 215,216
Total minus those rows:             83,556

7. Do the results agree? If not, which one is wrong and why?

The results do agree and both rach an answer of 83,556!

8. Why is it useful to verify a count using subtraction rather than direct filtering?

Using subtraction as a second method is useful because it won't fall victim to the same typos or logic errors that a simple filter could, since it calculates the answer a completely different way. This helps confirm that a filter is correct in its found solution and not giving a false answer, because if both independently agree, that's much stronger evidence than either one alone.