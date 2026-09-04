# Prompt Engineering Comparison
## Strategy 1
### 1. Complete prompt
"How should a BI analyst communicate data limitations to a non-technical audience?"
### 2. First 150 Words
Frame limitations in terms of business impact, not methodology. Instead of saying "the sample size violates assumptions of normality" or "we have a 15% null rate in the source table," translate it into what it means for the decision at hand: "This estimate is based on a smaller sample than usual, so treat the exact number as a rough range rather than a precise figure" or "We're missing data for about 1 in 7 customers, so the trend might look slightly different once that gap is filled."

Use analogies and everyday language. Comparing a confidence interval to a weather forecast ("70% chance of rain" rather than "it will rain") or describing data lag as "this is last week's snapshot, not live" helps people grasp uncertainty without needing statistical vocabulary.

Show, don't just tell. A simple visual — shaded confidence bands on a chart, a "data as of" timestamp, or a footnote flagging excluded records...
### 3. My Evaluation 
## Strategy 2
### 1. Complete prompt
"You are a senior credit risk analyst explaining data limitations to your family at Christmas dinner. How should you communicate this to them?"
### 2. First 150 Words
The core trick is to swap statistical vocabulary for everyday equivalents your family already reasons with, then use a story they'd recognize.

Start with what "data limitations" actually means in credit risk, translated: your models are only as good as the loan applications you've actually seen and how they turned out. If you say "our sample has survivorship bias," nobody's ears perk up. If you say "the bank's data only shows us the people who applied for and got loans — we don't see the great borrowers who never bothered applying, or how the people we rejected would have actually done," that lands, because everyone's had the experience of judging a situation from incomplete information (like judging a restaurant only from the one bad Yelp review someone left).

A few analogies that tend to work well around a dinner table:

The rearview mirror problem — your risk model is built entirely on 
### 3. My Evaluation
## Strategy 3
### 1. Complete prompt
"In a list, give me 10 ways a BI analyst should communicate data limitations to a non-technical audience?"
### 2. First 150 Words
1.	Lead with the "so what," not the caveat. Say what the limitation means for their decision before you explain the technical reason — "this number could be off by 10% either way, so I wouldn't use it to justify a big budget cut" lands better than opening with sample size math. 
2.	 Use a familiar analogy instead of statistical vocabulary. Swap "selection bias" for "we only hear from customers who bothered to fill out the survey, so we're missing everyone who just quietly left." 
3.	Give a confidence range instead of a false-precision number. "Somewhere between 800 and 950 customers, most likely around 870" is more honest and more usable than a single decimal-point figure that implies certainty you don't have. 
4.	Show, don't just tell — put the caveat on the chart itself. A shaded band around a trend line or a footnote under a KPI card ("excludes returns processed after March") reaches people who'd skim past a verbal disclaimer.
### 3. My Evaluation
