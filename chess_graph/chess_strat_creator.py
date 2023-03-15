import copy
import json
import random
import time
from typing import List, Dict

import yaml
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from yaml import load, SafeLoader
from pydantic import BaseModel
from bs4 import BeautifulSoup
import pandas as pd
import chess
import chess.engine
from stockfish import Stockfish
from sklearn.preprocessing import QuantileTransformer, MinMaxScaler

class Move(BaseModel):
    move_id: str
    parent_board_state_fen: str
    post_move_board_state_fen: str
    turn_to_move: str
    turn_count: int
    san_move: str
    uci_move: str
    win_prob: float
    play_percentage: int
    average_rating: int
    stock_fish: float

class Settings(BaseModel):
    max_moves_for_own_color: int
    min_perc_for_own_color_move: float
    max_moves_for_opposing_color: int
    min_move_perc_for_opposing_color: float
    max_move: int
    driver_path: str

    move_selection_rating_weight: float
    move_selection_win_perc_weight: float
    move_selection_stockfish_weight: float
    move_selection_popularity_weight: float

    move_selection_rating_preprocessing: str
    move_selection_win_perc_preprocessing: str
    move_selection_stockfish_preprocessing: str
    move_selection_popularity_preprocessing: str

    starting_board_config: str
    engine_path: str
    output_directory: str


preset_moves = {
    'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1': 'e4',
    'rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2': 'f4',
    'rnbqkbnr/pppppppp/8/8/3P4/8/PPP1PPPP/RNBQKBNR b KQkq - 0 1': 'e5',
    'rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1': 'd5'
}

def get_driver(driver_path: str):
    # options = Options()
    # options.headless = True
    # driver = webdriver.Chrome(chrome_path, options=options)
    return webdriver.Chrome(executable_path=driver_path)


def get_analysis_board(driver_path: str):
    driver = get_driver(driver_path=driver_path)
    driver.get('https://lichess.org/analysis')
    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR,
                                        '#main-wrap > main > div.analyse__controls.analyse-controls > div.features > button:nth-child(1)'))
    ).click()
    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR,
                                        '#main-wrap > main > div.analyse__tools > section > div.data > div > button:nth-child(2)'))
    ).click()
    # WebDriverWait(driver, 10).until(
    #     EC.presence_of_element_located((By.CSS_SELECTOR,
    #                                     '#main-wrap > main > div.analyse__tools > div.ceval > div > label'))
    # ).click()

    return driver


def get_settings() -> Settings:
    with open('settings.yml', 'r') as file:
        settings = yaml.safe_load(file)
        return Settings(**settings)


def standardize_field(df:pd.DataFrame, column: str, standardization: str, color: str) -> pd.DataFrame:
    if standardization == 'none':
        df[f'{column}_standardized'] = df[column]
    elif standardization == 'quantile':
        df[f'{column}_standardized'] = QuantileTransformer().fit_transform(df[column].values.reshape(-1, 1))
    elif standardization =='min_max_inversed_for_black':
        df[f'{column}_standardized'] = MinMaxScaler().fit_transform(df[column].values.reshape(-1, 1))
        if color == 'b':
            df[f'{column}_standardized'] = 1 - df[f'{column}_standardized']
    elif standardization == 'quantile_inversed_for_black':
        df[f'{column}_standardized'] = QuantileTransformer().fit_transform(df[column].values.reshape(-1, 1))
        if color == 'b':
            df[f'{column}_standardized'] = 1 - df[f'{column}_standardized']
    else:
        raise Exception(f'Standardization {standardization} not implemented')
    return df


def get_active_color(fen: str) -> str:
    if fen.split(' ')[1] == 'w':
        return 'w'
    elif fen.split(' ')[1] == 'b':
        return 'b'
    else:
        raise Exception(f'Invalid fen {fen}')


def play_moves(driver, position: str, settings: Settings, color: str) -> List[Move]:
    driver.find_element(By.CSS_SELECTOR, '#main-wrap > main > div.analyse__underboard > div > div.pair > input').click()
    driver.find_element(By.CSS_SELECTOR, '#main-wrap > main > div.analyse__underboard > div > div.pair > input').send_keys(position)
    driver.find_element(By.CSS_SELECTOR,
                        '#main-wrap > main > div.analyse__underboard > div > div.pair > input').send_keys(Keys.ENTER)
    time.sleep(1)
    soup = BeautifulSoup(driver.page_source)
    moves_table = soup.find('table', {'class': 'moves'})
    moves = moves_table.find_all('tr')

    active_color = get_active_color(position)

    move_dicts = list()
    for move in moves[1:-1]:
        uci_move = move['data-uci']
        san_move = move.find_all('td')[0].text
        perc_played = float(move.find_all('td')[1]['title'].replace('%', ''))/100
        avg_rating = int(move.find_all('td')[2]['title'].replace(',', '').split(':')[-1].strip())
        if color == 'w':
            win_perc = float(move.find_all('td')[2].find_all('span')[0]['style'].split(':')[-1].strip().replace('%', ''))/100
        if color == 'b':
            win_perc = float(move.find_all('td')[2].find_all('span')[2]['style'].split(':')[-1].strip().replace('%', ''))/100

        move_dicts.append(dict(uci_move=uci_move,
                               san_move=san_move,
                               perc_played=perc_played,
                               avg_rating=avg_rating,
                               win_perc=win_perc
                               ))

        move.find_all('td')

    move_df = pd.DataFrame.from_dict(move_dicts)

    if color == active_color:
        move_df = move_df[move_df['perc_played'] >= settings.min_perc_for_own_color_move]
    else:
        move_df = move_df[move_df['perc_played'] >= settings.min_move_perc_for_opposing_color]

    if position in preset_moves and color == active_color:
        move_df = move_df[move_df['san_move'] == preset_moves[position]]

    move_df['engine_score'] = 0

    for idx, row in move_df.iterrows():
        board = chess.Board(position)
        engine = chess.engine.SimpleEngine.popen_uci(settings.engine_path)
        engine_score = engine.analyse(board, limit=chess.engine.Limit(time=1.0))['score'].relative.cp
        move_df.loc[idx, 'engine_score'] = int(engine_score)
        engine.quit()

    standardize_field(move_df, 'avg_rating', settings.move_selection_rating_preprocessing, active_color)
    standardize_field(move_df, 'win_perc', settings.move_selection_win_perc_preprocessing, active_color)
    standardize_field(move_df, 'perc_played', settings.move_selection_popularity_preprocessing, active_color)
    standardize_field(move_df, 'engine_score', settings.move_selection_stockfish_preprocessing, active_color)

    move_df['score'] = 0
    move_df['score'] += move_df['avg_rating_standardized']* settings.move_selection_rating_weight
    move_df['score'] += move_df['win_perc_standardized'] * settings.move_selection_win_perc_weight
    move_df['score'] += move_df['perc_played_standardized']* settings.move_selection_popularity_weight
    move_df['score'] += move_df['engine_score_standardized'] * settings.move_selection_stockfish_weight

    if color == active_color:
        move_df = move_df.sort_values(by = ['score'], ascending = [False])
    else:
        move_df = move_df.sort_values(by=['perc_played'], ascending=[False])

    if color == active_color:
        move_df = move_df.iloc[:settings.max_moves_for_own_color]
    else:
        move_df = move_df.iloc[:settings.max_moves_for_opposing_color]

    returned_moves = list()

    print(f'picked moved: {position} {move_df.iloc[0].to_dict()}')

    for idx, row in move_df.iterrows():
        board = chess.Board(position)
        board.push_san(row["san_move"])
        san_move: str
        uci_move: str
        returned_moves.append(Move(**dict(move_id=f'{position}_{row["uci_move"]}',
                                    parent_board_state_fen = position,
                                    post_move_board_state_fen=board.fen(),
                                    turn_to_move = active_color,
                                    turn_count= position.split(' ')[-1],
                                    san_move=row["san_move"],
                                    uci_move=row["uci_move"],
                                    win_prob=row['win_perc'],
                                    average_rating=row['avg_rating'],
                                    stock_fish=row['engine_score'],
                                    play_percentage=row['perc_played'])))

    return returned_moves


def save_calculated_moves(move_dict: Dict, save_dir: str, color: str):
    move_dict_copy = copy.deepcopy(move_dict)
    for k in move_dict_copy.keys():
        move_dict_copy_l = copy.deepcopy(move_dict_copy[k])
        move_dict_copy[k] = [i.dict() for i in move_dict_copy_l]

    with open(f'{save_dir}/{color}_1.json', 'w') as f:
        json.dump(move_dict_copy, f)


def load_calculated_moves(save_dir: str, color: str):
    with open(f'{save_dir}/{color}_1.json', 'r') as f:
        move_dict = json.load(f)

    for k in move_dict.keys():
        move_dict_copy_l = copy.deepcopy(move_dict[k])
        move_dict[k] = [Move(**i) for i in move_dict_copy_l]
    return move_dict


def play(color: str):
    settings = get_settings()
    driver = get_analysis_board(settings.driver_path)

    try:
        moves = load_calculated_moves(settings.output_directory, color)
    except:
        moves = dict()
    moves = dict()

    while True:
        try:
            if len(list(moves.keys())) == 0:
                moves[settings.starting_board_config] = play_moves(driver,
                                                                   settings.starting_board_config,
                                                                   settings=settings,
                                                                   color=color)
                continue

            moves_with_unsolved_boards = list()
            for bc, move_list in moves.items():
                for move in move_list:
                    if move.post_move_board_state_fen not in moves.keys() and move.turn_count < settings.max_move:
                        moves_with_unsolved_boards.append(move)

            if len(moves_with_unsolved_boards) == 0:
                break

            moves_with_unsolved_boards = sorted(moves_with_unsolved_boards, key = lambda x: int(x.parent_board_state_fen.split(' ')[-1]))
            picked_move_with_unsolved_board = moves_with_unsolved_boards[0]
            moves[picked_move_with_unsolved_board.post_move_board_state_fen] = play_moves(driver,
                       picked_move_with_unsolved_board.post_move_board_state_fen,
                       settings=settings,
                       color=color)
            save_calculated_moves(moves, settings.output_directory, color)
            print(f'boards saved: {len(moves.keys())}')
        except Exception as e:
            print(f'{e}')
            time.sleep(20)
            driver = get_analysis_board(settings.driver_path)


def engine_test():
    engine = chess.engine.SimpleEngine.popen_uci("/usr/local/Cellar/stockfish/15.1/bin/stockfish")

    board = chess.Board()
    while not board.is_game_over():
        result = engine.play(board, chess.engine.Limit(time=0.1))
        board.push(result.move)
        print(result.move)

    engine.quit()

if __name__ == '__main__':
    play('b')
    play('w')
