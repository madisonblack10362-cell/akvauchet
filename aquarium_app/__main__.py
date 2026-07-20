"""Точка входа: python -m aquarium_app"""
from aquarium_app.gui.app import App


def main():
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()