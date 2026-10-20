"""Explicitly opt-in, tools-disabled Copilot CLI text provider for HS project AI.

This executes an existing configured identity as a text model, not an engineering
 tool runner. Its claims remain proposals subject to all HS authority gates.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from typing import Any

_ALLOWED_BINARIES = frozenset({'copilot-spectator26', 'copilot-spectator', 'copilot-ly', 'copilot-ly2'})


def copilot_cli_configured() -> bool:
    binary=os.getenv('HARDWARE_SPLICER_COPILOT_CLI_BINARY','copilot-spectator26')
    return binary in _ALLOWED_BINARIES and shutil.which(binary) is not None


def call_copilot_cli_chat(prompt: str, *, model: str | None = None,
                          stage: str | None = None, temperature: float = 0,
                          json_mode: bool = False, timeout_s: int = 90,
                          system: str | None = None) -> dict[str, Any]:
    binary=os.getenv('HARDWARE_SPLICER_COPILOT_CLI_BINARY','copilot-spectator26')
    if binary not in _ALLOWED_BINARIES:
        return {'ok':False,'error':'copilot_cli_binary_not_allowlisted'}
    if shutil.which(binary) is None:
        return {'ok':False,'error':'copilot_cli_not_available'}
    # System policy is carried explicitly in the prompt because this CLI accepts
    # a single message in non-interactive mode. No shell expansion or tool access.
    message=((system or '')+'\n\n'+prompt).strip()
    if json_mode:
        message+='\n\nReturn ONLY a single valid JSON object. No Markdown fences or explanatory prose.'
    argv=[binary,'-p',message,'--silent','--available-tools','none','--no-color',
          '--no-custom-instructions','--model',model or 'auto']
    try:
        completed=subprocess.run(argv,cwd='/tmp',capture_output=True,text=True,
                                 timeout=min(max(int(timeout_s),1),120),check=False)
    except subprocess.TimeoutExpired:
        return {'ok':False,'error':'copilot_cli_timeout'}
    except OSError as exc:
        return {'ok':False,'error':'copilot_cli_execution_error', 'message':type(exc).__name__}
    if completed.returncode:
        return {'ok':False,'error':'copilot_cli_nonzero_exit','returncode':completed.returncode}
    content=completed.stdout.strip()
    if content.startswith('```'):
        content='\n'.join(content.splitlines()[1:-1]).strip()
    if not content:
        return {'ok':False,'error':'copilot_cli_empty_response'}
    if json_mode:
        try:
            if not isinstance(json.loads(content),dict):raise ValueError('not a JSON object')
        except (json.JSONDecodeError,ValueError):
            return {'ok':False,'error':'copilot_cli_invalid_json'}
    return {'ok':True,'provider':'copilot_cli','model':model or 'auto',
            'content':content,'usage':{'tokens_reported':False}}
