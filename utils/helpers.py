def expectsEmpty(question: str) -> bool:
    """Check if question expects empty results"""
    emptyKeywords = ['never', 'no ', 'none',
                     'zero', 'empty', 'without', 'don\'t', 'not']
    return any(kw in question.lower() for kw in emptyKeywords)
