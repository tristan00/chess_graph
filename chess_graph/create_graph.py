from chess_strat_creator import load_calculated_moves, get_settings, get_active_color, get_move_count
import graphviz

def get_board(fen: str):
    settings = get_settings()
    moves = load_calculated_moves(settings.output_directory, 'b')
    moves_fen = moves[fen]
    moves_fen


def make_graph(color, starting_position, max_depth = 3):
    settings = get_settings()
    moves = load_calculated_moves(settings.output_directory, color)
    dot = graphviz.Digraph(comment=color)

    starting_turn_count = None
    for state in moves.keys():
        if moves[state].fen == starting_position:
            starting_turn_count = moves[state].turn_count
    assert starting_turn_count is not None

    move_count = get_move_count(starting_position)

    for state in moves.keys():
        for move in moves[state]:
            if move.parent_board_state_fen in moves.keys() and move.move_count < move_count+max_depth:
                dot.edge(move.parent_board_state_fen, move.post_move_board_state_fen, label=move.uci_move)

    dot.render(f'{settings.output_directory}/{color}_viz.gv')


def print_game(fen):
    settings = get_settings()
    moves = load_calculated_moves(settings.output_directory, get_active_color(fen))

if __name__ == '__main__':
    # get_board('rnbqkbnr/pppp1ppp/8/4P3/8/8/PPP1PPPP/RNBQKBNR b KQkq - 0 2')
    make_graph('w', 'rnbqkbnr/pppp1ppp/8/4P3/8/8/PPP1PPPP/RNBQKBNR b KQkq - 0 2')