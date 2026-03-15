#!/usr/bin/env bash

cloc . --exclude-dir=venv,__pycache__,.git,.claude --include-lang=Python,Markdown,TOML,Shell
