# Prompt Engineering Comparison
## Strategy 1
### 1. Complete prompt
"How should a BI analyst communicate data limitations to a non-technical audience?"
### 2. First 150 Words
Frame limitations in terms of business impact, not methodology. Instead of saying "the sample size violates assumptions of normality" or "we have a 15% null rate in the source table," translate it into what it means for the decision at hand: "This estimate is based on a smaller sample than usual, so treat the exact number as a rough range rather than a precise figure" or "We're missing data for about 1 in 7 customers, so the trend might look slightly different once that gap is filled."

Use analogies and everyday language. Comparing a confidence interval to a weather forecast ("70% chance of rain" rather than "it will rain") or describing data lag as "this is last week's snapshot, not live" helps people grasp uncertainty without needing statistical vocabulary.

Show, don't just tell. A simple visual — shaded confidence bands on a chart, a "data as of" timestamp, or a footnote flagging excluded records...
### 3. My Evaluation 
I think Claude's answer to this prompt was not bad; it gave a broad overview of the topic, and I think it was a good starting point for someone brainstorming answers to this question. That said, even though the suggestions were good, the examples weren't fully fleshed out, and a follow-up question for each category would be needed before a BI analyst could form a clear idea of how to communicate data limitations. 
## Strategy 2
### 1. Complete prompt
"You are a senior credit risk analyst explaining data limitations to your family at Christmas dinner. How should you communicate this to them?"
### 2. First 150 Words
The core trick is to swap statistical vocabulary for everyday equivalents your family already reasons with, then use a story they'd recognize.

Start with what "data limitations" actually means in credit risk, translated: your models are only as good as the loan applications you've actually seen and how they turned out. If you say "our sample has survivorship bias," nobody's ears perk up. If you say "the bank's data only shows us the people who applied for and got loans — we don't see the great borrowers who never bothered applying, or how the people we rejected would have actually done," that lands, because everyone's had the experience of judging a situation from incomplete information (like judging a restaurant only from the one bad Yelp review someone left).

A few analogies that tend to work well around a dinner table:

The rearview mirror problem — your risk model is built entirely on 
### 3. My Evaluation
When it comes to explanation and examples, Claude responded more effectively to this prompt than the latter. It really broke down what family members at the table will not understand, how to make them understand, and also how to respond to common follow-up questions without getting frustrated. What I did not like about this response was its formatting: it gave the advice in bulky paragraphs, so if you wanted to find a specific piece of information, you had to reread the whole response.  
## Strategy 3
### 1. Complete prompt
"In a list, give me 10 ways a BI analyst should communicate data limitations to a non-technical audience?"
### 2. First 150 Words
1. Lead with the takeaway, not the caveat. State the finding first, then the limitation — "Sales grew 12% last quarter, though this excludes returns processed after March 15" — so the limitation doesn't bury the insight. 
2.	Use analogies instead of statistical jargon. Swap "margin of error" for something like "this number could be off by a little, similar to how a weather forecast isn't exact down to the degree." 
3.	Show a confidence range visually. A shaded band around a trend line or a simple "low/likely/high" range communicates uncertainty faster than a written explanation of standard error. 
4.	Translate sample size into everyday terms. Instead of "n=42," say "this is based on a small group of customers, so it might not represent everyone" — the concern registers immediately.
5.	Name the gap in plain terms, not the technical cause. "We don't have data on walk-in customers, only online orders" lands better than "the dataset excludes non-digitized POS transactions."
### 3. My Evaluation
This response was extremely readable and organized and gave good examples for each bullet point. But it didn't go in-depth on each point, like the previous two, which means more tokens would need to be used on follow-up questions. 
## Conclusion section
Personally, I think that strategy 3 produced the best response for a BI analyst. Although follow-up questions may be needed, that's OK when you consider how much time will be saved because it is organized and easy to read. Also, because of the format, follow-up questions will not have to be long (i.e., give another example of idea 6). In comparison, prompt 2 would have to cite a specific example or point in words (i.e give me another way to respond to the "who gets counted" problem); this would use up more tokens and valuable time. Overall, I think strategy 3 is a better version of prompt 1 in terms of content and is more organized than prompt 2, making it the best option of the 3 for a BI analyst. 
## Fact-Check
### 1. The Exact 
"In industry practice, delinquency is usually tracked in buckets (30/60/90+ days past due) precisely because it's a transitional state — the longer it persists, the more likely it is to become unrecoverable."
### 2. The Source I Used
https://www.investopedia.com/terms/r/roll-rate.asp#:~:text=In%20the%20credit%20card%20industry%2C%20creditors,late%20and%20so%20on%20up%20to%20charge-off. 
### 3. What the source says
"Credit card issuing banks estimate credit losses by segregating their overall credit card portfolio into delinquency "buckets," similar to the 60-day, 90-day categories mentioned earlier. A bank's management measures roll rates for the current month and current quarter, or averages several months or quarters to smooth out fluctuations. Roll rates may also be further broken down by product category or borrower quality to gain a better understanding of delinquencies overall."
### 4. Agree/Disagree
I believe these statements agree with each other, and I do not believe Claude's statement was false, but it was extremely hard to find this term in any approved sources or peer-reviewed articles. I did find it on some websites and in a pamphlet by MBA.org, but there wasn't much else. This led me to use an article about delinquency in credit card debt, not in loans. Claude's use of this term made me think it was much more common finance jargon than it actually was. This means that although Claud is not giving me false information, I still have to be conscious of the information's relevance.
