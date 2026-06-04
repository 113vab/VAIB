# V.A.I.B. Custom Plugin Example
# To add new tools, write a python function and decorate it with @vaib_tool.
# The tool name, docstring, and argument types will be automatically bound to V.A.I.B.'s brain.

from app.tools.plugins import vaib_tool

@vaib_tool
def get_weather_forecast(location: str) -> str:
    """
    Retrieve the weather forecast for a specified city or location.
    
    Args:
        location: The city and/or country to query the weather for (e.g. 'London', 'Tokyo, Japan').
    """
    # Mock weather response for demonstration
    return f"The current forecast for {location} is 22°C (72°F) with clear sunny skies, Sir. A perfect day for productivity."

@vaib_tool
def roll_dice(sides: int = 6) -> str:
    """
    Roll a virtual multi-sided dice and return the outcome.
    
    Args:
        sides: The number of sides on the dice (default is 6).
    """
    import random
    result = random.randint(1, sides)
    return f"I've rolled a {sides}-sided dice for you, Sir. The outcome is: {result}."
