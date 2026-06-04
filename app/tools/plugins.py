import os
import sys
import inspect
import logging
import importlib.util
from pathlib import Path
from typing import Dict, Callable, Any

logger = logging.getLogger("vaib")

# Global registry mapping tool_name -> callable function
plugin_registry: Dict[str, Callable[..., Any]] = {}

def vaib_tool(func):
    """
    Decorator to mark a custom function as an extensible V.A.I.B. tool.
    The function must have descriptive docstrings and type-annotated arguments
    so that Google Gemini can correctly build its tool-calling schema.
    """
    plugin_registry[func.__name__] = func
    logger.info(f"Successfully registered plugin tool: '{func.__name__}' via decorator.")
    return func

def create_example_plugin(plugins_dir: Path):
    """Creates a template/example plugin file to demonstrate custom tool creation."""
    example_path = plugins_dir / "example_plugin.py"
    if example_path.exists():
        return
        
    example_content = """# V.A.I.B. Custom Plugin Example
# To add new tools, write a python function and decorate it with @vaib_tool.
# The tool name, docstring, and argument types will be automatically bound to V.A.I.B.'s brain.

from app.tools.plugins import vaib_tool

@vaib_tool
def get_weather_forecast(location: str) -> str:
    \"\"\"
    Retrieve the weather forecast for a specified city or location.
    
    Args:
        location: The city and/or country to query the weather for (e.g. 'London', 'Tokyo, Japan').
    \"\"\"
    # Mock weather response for demonstration
    return f"The current forecast for {location} is 22°C (72°F) with clear sunny skies, Sir. A perfect day for productivity."

@vaib_tool
def roll_dice(sides: int = 6) -> str:
    \"\"\"
    Roll a virtual multi-sided dice and return the outcome.
    
    Args:
        sides: The number of sides on the dice (default is 6).
    \"\"\"
    import random
    result = random.randint(1, sides)
    return f"I've rolled a {sides}-sided dice for you, Sir. The outcome is: {result}."
"""
    try:
        example_path.write_text(example_content, encoding="utf-8")
        logger.info("Created example plugin template at: %s", example_path)
    except Exception as e:
        logger.error(f"Failed to create example plugin: {e}")

def load_plugins(project_root: Path):
    """
    Scans the /plugins/ directory in the project root, executes any .py plugin modules,
    and dynamically populates the tool registry.
    """
    plugins_dir = project_root / "plugins"
    if not plugins_dir.exists():
        try:
            plugins_dir.mkdir(parents=True, exist_ok=True)
            logger.info("Created plugins directory at: %s", plugins_dir)
        except Exception as e:
            logger.error(f"Failed to create plugins folder: {e}")
            return
            
    create_example_plugin(plugins_dir)
    
    # Add plugins folder to python path so modules can import correctly
    sys_path_added = False
    resolved_path_str = str(plugins_dir.resolve())
    if resolved_path_str not in sys.path:
        sys.path.append(resolved_path_str)
        sys_path_added = True
        
    try:
        for file_path in plugins_dir.glob("*.py"):
            if file_path.name.startswith("__"):
                continue
                
            module_name = file_path.stem
            try:
                # Dynamically load the module using importlib
                spec = importlib.util.spec_from_file_location(module_name, str(file_path))
                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)
                    # Add to sys.modules to prevent double loading
                    sys.modules[module_name] = module
                    spec.loader.exec_module(module)
                    logger.info(f"Loaded plugin module: '{module_name}'")
            except Exception as mod_err:
                logger.error(f"Failed to load plugin module '{module_name}': {mod_err}")
    finally:
        # We keep the path in sys.path for loaded modules to function, but we can clean up if desired.
        pass
