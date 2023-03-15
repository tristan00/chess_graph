from chess_graph.chess_strat_creator import load_calculated_moves, get_settings


def get_board(fen: str):
    settings = get_settings()
    moves = load_calculated_moves(settings.output_directory, 'b')
    moves_fen = moves[fen]
    moves_fen


if __name__ == '__main__':
    get_board('rnbqkbnr/pppp1ppp/8/4P3/8/8/PPP1PPPP/RNBQKBNR b KQkq - 0 2')