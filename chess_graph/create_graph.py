from chess_graph.chess_strat_creator import load_calculated_moves, get_settings

if __name__ == '__main__':
    settings = get_settings()
    moves = load_calculated_moves(settings.output_directory, 'b')
    moves