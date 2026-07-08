def categorize_market(title):
    text = title.lower()

    if any(word in text for word in ["rain", "snow", "temperature", "weather"]):
        return "Weather"
    if any(word in text for word in ["fed", "inflation", "cpi", "rate"]):
        return "Economics"
    if any(word in text for word in ["trump", "biden", "election", "president"]):
        return "Politics"
    if any(word in text for word in ["bitcoin", "btc", "ethereum", "stock", "s&p"]):
        return "Finance"

    return "Other"