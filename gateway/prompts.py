import os
import yaml
from pathlib import Path
from typing import Dict, Any
from jinja2 import Environment, FileSystemLoader, Template

from shared.config import config


class PromptManager:
    def __init__(self, prompts_dir: str = "prompts"):
        self.prompts_dir = Path(prompts_dir)
        self.jinja_env = Environment(
            loader=FileSystemLoader(self.prompts_dir),
            trim_blocks=True,
            lstrip_blocks=True
        )
        self._prompt_cache = {}
    
    async def get_prompt(self, prompt_path: str, variables: Dict[str, Any] = None) -> str:
        variables = variables or {}
        
        cache_key = f"{prompt_path}_{hash(str(sorted(variables.items())))}"
        if cache_key in self._prompt_cache:
            template = self._prompt_cache[cache_key]
        else:
            template = await self._load_prompt_template(prompt_path)
            self._prompt_cache[cache_key] = template
        
        return template.render(**variables)
    
    async def _load_prompt_template(self, prompt_path: str) -> Template:
        yaml_path = f"{prompt_path}.yaml"
        
        try:
            template = self.jinja_env.get_template(yaml_path)
            content = template.render()
            
            prompt_data = yaml.safe_load(content)
            
            if isinstance(prompt_data, dict) and "template" in prompt_data:
                prompt_text = prompt_data["template"]
            else:
                prompt_text = content
            
            return Template(prompt_text)
            
        except Exception as e:
            fallback_text = f"Error loading prompt {prompt_path}: {e}. Please provide a response based on the user's request."
            return Template(fallback_text)
    
    def reload_cache(self):
        self._prompt_cache.clear()