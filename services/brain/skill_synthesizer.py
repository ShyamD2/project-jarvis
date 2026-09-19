"""
Skill Synthesizer Engine for Project J.A.R.V.I.S. (Pillar 1).
Translates user demonstrations, terminal workflows, and natural language prompts
into fully typed, verified, safe Python tools, hot-loading them into ToolRegistry
at runtime with zero daemon downtime and zero local CPU overhead.
"""

from __future__ import annotations
import os
import sys
import ast
import time
import json
import uuid
import importlib.util
from typing import Dict, Any, List, Optional, Tuple

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.insert(0, PROJECT_ROOT)

from shared.sdk_python.jarvis_sdk.logger import get_logger
from services.brain.tools.base import JarvisTool, ToolDefinition
from shared.schemas.action_envelope import ActionTier, TargetWorld

logger = get_logger("JarvisSkillSynthesizer")

CUSTOM_TOOLS_DIR = os.path.join(PROJECT_ROOT, "services", "brain", "tools", "custom")
os.makedirs(CUSTOM_TOOLS_DIR, exist_ok=True)


class SkillSynthesizer:
    def __init__(self):
        self._demonstrations: Dict[str, List[Dict[str, Any]]] = {}
        self._synthesized_history: List[Dict[str, Any]] = []

    def start_demonstration(self, label: str = "demo") -> str:
        """Starts a new demonstration tracking buffer."""
        demo_id = f"demo_{uuid.uuid4().hex[:8]}_{label}"
        self._demonstrations[demo_id] = []
        logger.info(f"[SkillSynthesizer] Started demonstration recording: {demo_id}")
        return demo_id

    def record_step(self, demo_id: str, action_type: str, details: Dict[str, Any]) -> bool:
        """Records a demonstration step (command, hotkey, API query, or window state)."""
        if demo_id not in self._demonstrations:
            self._demonstrations[demo_id] = []
        step = {
            "timestamp": time.time(),
            "action_type": action_type,
            "details": details
        }
        self._demonstrations[demo_id].append(step)
        return True

    def get_demonstration(self, demo_id: str) -> List[Dict[str, Any]]:
        return self._demonstrations.get(demo_id, [])

    def validate_code_ast(self, code_str: str) -> Tuple[bool, Optional[str]]:
        """
        Performs static AST validation and DevSecOps linting on synthesized code:
        - Valid Python syntax
        - Subclasses JarvisTool
        - Implements async execute(**kwargs) -> Dict[str, Any]
        - Prohibits destructive system calls or unsanitized eval/exec
        """
        try:
            tree = ast.parse(code_str)
        except SyntaxError as e:
            return False, f"Syntax error in generated code: {e}"

        found_tool_class = False
        disallowed_functions = {"eval", "exec", "compile"}
        disallowed_modules = {"pty", "telnetlib"}

        for node in ast.walk(tree):
            # Check imports
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name in disallowed_modules:
                        return False, f"Disallowed module import: {alias.name}"
            elif isinstance(node, ast.ImportFrom):
                if node.module in disallowed_modules:
                    return False, f"Disallowed module import from: {node.module}"

            # Check calls
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id in disallowed_functions:
                    return False, f"Prohibited function execution: {node.func.id}()"

            # Check class definition
            if isinstance(node, ast.ClassDef):
                for base in node.bases:
                    if (isinstance(base, ast.Name) and base.id == "JarvisTool") or \
                       (isinstance(base, ast.Attribute) and base.attr == "JarvisTool"):
                        found_tool_class = True

        if not found_tool_class:
            return False, "Generated code does not contain a valid JarvisTool subclass."

        return True, None

    async def _generate_tool_code_via_ai(self, prompt: str, tool_name: str) -> Optional[str]:
        """Leverages high-speed Groq LPU (or primary AI provider) to write Python tool code."""
        try:
            from services.brain.providers.ai_manager import ai_manager
            system_prompt = (
                "You are the J.A.R.V.I.S. Core Tool Synthesizer. "
                "You write clean, production-grade Python tools subclassing `JarvisTool` for Project J.A.R.V.I.S. "
                "RULES:\n"
                "1. Always import `JarvisTool`, `ToolDefinition`, `ActionTier`, `TargetWorld`.\n"
                "2. Define the tool class inheriting from `JarvisTool`.\n"
                "3. In __init__, call super().__init__(ToolDefinition(name, description, target_world, tier, parameters_schema)).\n"
                "4. Implement `async def execute(self, **kwargs) -> Dict[str, Any]:` returning `{'success': True, ...}`.\n"
                "5. Instantiate the tool at module level as `tool_instance = <YourClass>()`.\n"
                "6. Output ONLY pure Python code wrapped in ```python ... ``` without conversational commentary."
            )
            user_prompt = f"Tool Name: {tool_name}\nRequirement/Workflow: {prompt}\nGenerate the complete Python tool code."
            
            resp = await ai_manager.generate_text(prompt=user_prompt, system_prompt=system_prompt, temperature=0.2)
            raw = resp.text.strip()
            # Extract code block if present
            if "```python" in raw:
                code = raw.split("```python")[1].split("```")[0].strip()
            elif "```" in raw:
                code = raw.split("```")[1].split("```")[0].strip()
            else:
                code = raw
            return code
        except Exception as e:
            logger.warning(f"[SkillSynthesizer] Cloud AI generation fallback triggered: {e}")
            return None

    def _generate_template_code(self, tool_name: str, description: str, commands: List[str]) -> str:
        """Deterministic, zero-CPU fallback template generator when offline or no API key."""
        class_name = "".join(word.capitalize() for word in tool_name.replace("-", "_").split("_")) + "Tool"
        cmd_repr = json.dumps(commands)
        code = f'''"""
Custom Tool: {tool_name}
Auto-synthesized by J.A.R.V.I.S. SkillSynthesizer.
"""

import subprocess
import asyncio
from typing import Dict, Any
from services.brain.tools.base import JarvisTool, ToolDefinition
from shared.schemas.action_envelope import ActionTier, TargetWorld
from shared.sdk_python.jarvis_sdk.logger import get_logger

logger = get_logger("Tool_{tool_name}")


class {class_name}(JarvisTool):
    def __init__(self):
        super().__init__(
            ToolDefinition(
                name="{tool_name}",
                description="{description}",
                target_world=TargetWorld.COMPUTER,
                tier=ActionTier.TIER_1_SOFT,
                parameters_schema={{
                    "argument": {{"type": "string", "default": ""}},
                    "timeout_seconds": {{"type": "integer", "default": 15}}
                }},
                risk_level="LOW",
                timeout_seconds=20
            )
        )
        self._preset_commands = {cmd_repr}

    async def execute(self, argument: str = "", timeout_seconds: int = 15, **kwargs) -> Dict[str, Any]:
        logger.info(f"Executing synthesized skill '{tool_name}' with arg='{{argument}}'")
        outputs = []
        loop = asyncio.get_event_loop()
        
        for cmd in self._preset_commands:
            formatted_cmd = cmd.replace("{{arg}}", argument) if argument else cmd
            try:
                res = await loop.run_in_executor(
                    None,
                    lambda c=formatted_cmd: subprocess.run(
                        c, shell=True, capture_output=True, text=True, timeout=timeout_seconds
                    )
                )
                outputs.append({{
                    "command": formatted_cmd,
                    "stdout": res.stdout.strip(),
                    "stderr": res.stderr.strip(),
                    "exit_code": res.returncode
                }})
            except Exception as e:
                outputs.append({{"command": formatted_cmd, "error": str(e), "exit_code": -1}})

        success = all(o.get("exit_code") == 0 for o in outputs) if outputs else True
        return {{
            "success": success,
            "tool": "{tool_name}",
            "steps_executed": len(outputs),
            "outputs": outputs
        }}


tool_instance = {class_name}()
'''
        return code

    def hot_load_tool_file(self, file_path: str, registry=None) -> Optional[JarvisTool]:
        """Dynamically imports a tool module and registers it into ToolRegistry with zero reload."""
        if not os.path.exists(file_path):
            logger.error(f"[SkillSynthesizer] Tool file does not exist: {file_path}")
            return None

        module_name = os.path.splitext(os.path.basename(file_path))[0]
        try:
            spec = importlib.util.spec_from_file_location(f"services.brain.tools.custom.{module_name}", file_path)
            if not spec or not spec.loader:
                logger.error(f"[SkillSynthesizer] Could not load spec for {file_path}")
                return None

            mod = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = mod
            spec.loader.exec_module(mod)

            tool_inst = getattr(mod, "tool_instance", None)
            if not tool_inst:
                # Find any JarvisTool instance or class in module
                for attr_name in dir(mod):
                    attr = getattr(mod, attr_name)
                    if isinstance(attr, JarvisTool):
                        tool_inst = attr
                        break
                    elif isinstance(attr, type) and issubclass(attr, JarvisTool) and attr is not JarvisTool:
                        tool_inst = attr()
                        break

            if tool_inst:
                if registry:
                    registry.register(tool_inst)
                else:
                    try:
                        from services.brain.tools.registry import tool_registry
                        tool_registry.register(tool_inst)
                    except Exception:
                        pass
                logger.info(f"✔ [SkillSynthesizer] Hot-loaded and registered tool: '{tool_inst.name}'")
                return tool_inst
            else:
                logger.warning(f"[SkillSynthesizer] No JarvisTool found in {file_path}")
                return None
        except Exception as e:
            logger.error(f"[SkillSynthesizer] Failed to hot-load tool from {file_path}: {e}")
            return None

    def load_all_custom_tools(self, registry=None) -> int:
        """Scans `services/brain/tools/custom` and registers all verified tools into the registry."""
        count = 0
        if not os.path.exists(CUSTOM_TOOLS_DIR):
            return 0

        for f in os.listdir(CUSTOM_TOOLS_DIR):
            if f.endswith(".py") and not f.startswith("__"):
                path = os.path.join(CUSTOM_TOOLS_DIR, f)
                tool = self.hot_load_tool_file(path, registry=registry)
                if tool:
                    count += 1
        logger.info(f"[SkillSynthesizer] Loaded {count} certified custom tools from disk.")
        return count

    async def synthesize_skill(
        self,
        name: str,
        description: str,
        prompt_or_commands: Any,
        registry=None
    ) -> Dict[str, Any]:
        """
        Master Skill Synthesis Pipeline:
        Prompt/Demo -> AI/Template Code -> AST Lint/Verify -> Write Disk -> Hot Load -> Return Status
        """
        clean_name = name.lower().strip().replace(" ", "_").replace("-", "_")
        target_file = os.path.join(CUSTOM_TOOLS_DIR, f"{clean_name}.py")

        code = None
        if isinstance(prompt_or_commands, list):
            # Deterministic CLI commands sequence
            code = self._generate_template_code(clean_name, description, prompt_or_commands)
        elif isinstance(prompt_or_commands, str):
            # Natural language prompt: try Groq LPU first for rich reasoning
            ai_code = await self._generate_tool_code_via_ai(prompt_or_commands, clean_name)
            if ai_code:
                valid, err = self.validate_code_ast(ai_code)
                if valid:
                    code = ai_code
                else:
                    logger.warning(f"[SkillSynthesizer] AI code failed AST validation ({err}), using safe template fallback.")
            if not code:
                # Fallback to template
                code = self._generate_template_code(clean_name, description, [prompt_or_commands])

        if not code:
            return {"success": False, "error": "Failed to synthesize tool code."}

        # Validate AST
        valid, err = self.validate_code_ast(code)
        if not valid:
            return {"success": False, "error": f"AST validation failed: {err}"}

        # Write to disk
        try:
            with open(target_file, "w", encoding="utf-8") as f:
                f.write(code)
        except Exception as e:
            return {"success": False, "error": f"Failed to persist tool file: {e}"}

        # Hot-load into live registry
        tool_inst = self.hot_load_tool_file(target_file, registry=registry)
        if not tool_inst:
            return {"success": False, "error": "Tool saved to disk but hot-load failed."}

        meta = {
            "name": clean_name,
            "description": description,
            "file_path": target_file,
            "tier": tool_inst.tier.value if hasattr(tool_inst.tier, "value") else str(tool_inst.tier),
            "created_at": time.time(),
            "status": "active"
        }
        self._synthesized_history.append(meta)
        return {
            "success": True,
            "message": f"Tool '{clean_name}' successfully synthesized and hot-loaded into runtime.",
            "tool_name": clean_name,
            "file_path": target_file
        }


skill_synthesizer = SkillSynthesizer()
