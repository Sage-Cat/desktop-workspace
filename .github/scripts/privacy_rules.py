#!/usr/bin/env python3
"""Shared private-path, credential and attribution signatures."""
import json
from pathlib import PurePosixPath
import re
import sqlite3


PRIVATE_DIRECTORIES = {'.codex', '.claude', '.agents', '.cursor', 'logs', 'runtime',
                       'transcripts', 'checkpoints', 'snapshots', '.secrets',
                       'local', 'private', 'state', 'backups'}
PRIVATE_NAMES = {'claude.md', 'gemini.md', 'codex.md', 'credentials', 'credentials.json',
                 'credentials.toml', 'credentials.yaml', 'credentials.yml', 'secrets.json',
                 'secrets.toml', 'secrets.yaml', 'secrets.yml', 'id_rsa', 'id_ed25519',
                 'id_ecdsa', 'id_dsa', '.netrc', '.npmrc', '.pypirc'}
PRIVATE_SUFFIXES = {'.log', '.jsonl', '.db', '.sqlite', '.sqlite3', '.pem', '.key', '.p12', '.pfx'}
CREDENTIALS = [
    re.compile(rb'-----BEGIN (?:RSA |EC |DSA |OPENSSH |ENCRYPTED )?PRIVATE KEY-----'),
    re.compile(rb'\b(?:gh[pousr]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{40,})\b'),
    re.compile(rb'\b(?:AKIA|ASIA)[A-Z0-9]{16}\b'),
    re.compile(rb'\bsk-(?:proj-|ant-api\d{2}-)[A-Za-z0-9_-]{32,}\b'),
    re.compile(rb'\bxox[baprs]-[A-Za-z0-9-]{20,}\b'),
]
AI_NAMES = r'(?:codex|claude|chatgpt|copilot|gemini|openai|anthropic|cursor|aider|devin|\bAI\b)'
ATTRIBUTION = re.compile(
    r'(?im)^\s*(?:co-authored-by|signed-off-by):[^\n]*' + AI_NAMES
    + r'|(?:generated|written|authored|co-authored|assisted|created)\s+(?:by|with|using)\s+[^\n]{0,40}' + AI_NAMES
    + r'|\bAI[- ](?:generated|authored|assisted)\b')


def single_schema_statement(sql):
    if not re.match(r'^\s*CREATE\s+', sql, re.IGNORECASE):
        return False
    statement = ''
    count = 0
    for character in sql.rstrip().rstrip(';') + ';':
        statement += character
        if character == ';' and sqlite3.complete_statement(statement):
            count += 1
            statement = ''
    return count == 1 and not statement.strip()


def schema_only(data):
    try:
        entries = json.loads(data)
        return isinstance(entries, list) and all(
            isinstance(entry, list) and len(entry) == 4 and all(isinstance(value, str) for value in entry)
            and entry[0] in {'table', 'index', 'view', 'trigger'}
            and single_schema_statement(entry[3])
            for entry in entries)
    except (ValueError, UnicodeDecodeError):
        return False


def path_problem(path, data):
    parts = PurePosixPath(path.lower()).parts
    name = parts[-1]
    if (any(part in PRIVATE_DIRECTORIES for part in parts)
            or re.fullmatch(r'agents[^/]*\.md', name) or name in PRIVATE_NAMES
            or (len(parts) > 1 and parts[0] == '.github' and name.startswith('copilot-instructions'))):
        return 'private instruction, runtime, or credential path'
    if name == '.env' or name.startswith('.env.') or PurePosixPath(name).suffix in PRIVATE_SUFFIXES:
        return 'private data or key file'
    if name.endswith('.sqlite.schema.json'):
        if not (len(parts) == 3 and parts[:2] == ('tests', 'fixtures') and schema_only(data)):
            return 'database fixture is not schema-only'
    return None
