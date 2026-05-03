import argparse

from graph.graphcalc import GraphCalcApp


def main():
    parser = argparse.ArgumentParser(
        description='Graph Calculator — plot equations interactively.',
    )
    parser.add_argument(
        'equations', nargs='*', metavar='EQUATION',
        help='Equations to plot on launch, e.g. "y=x**2" "y=sin(x)"',
    )
    args = parser.parse_args()

    GraphCalcApp(initial_equations=args.equations or None).run()


if __name__ == '__main__':
    main()
