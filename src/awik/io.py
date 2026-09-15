"""Checkpoint helpers so each notebook can run independently, reading the previous
notebook's output instead of holding everything in one shared kernel session."""

import json
import os

import pandas as pd

# Notebooks execute with cwd = notebooks/ (Jupyter's default -- cwd is the
# directory holding the .ipynb file), so this is relative to that, not repo root.
INTERIM_DIR = '../data/interim'


def save_df(df, name, directory=INTERIM_DIR):
    os.makedirs(directory, exist_ok=True)
    df.to_csv(os.path.join(directory, f'{name}.csv'), index=False)


def load_df(name, directory=INTERIM_DIR):
    return pd.read_csv(os.path.join(directory, f'{name}.csv'))


def save_json(obj, name, directory=INTERIM_DIR):
    os.makedirs(directory, exist_ok=True)
    with open(os.path.join(directory, f'{name}.json'), 'w') as f:
        json.dump(obj, f)


def load_json(name, directory=INTERIM_DIR):
    with open(os.path.join(directory, f'{name}.json')) as f:
        return json.load(f)
