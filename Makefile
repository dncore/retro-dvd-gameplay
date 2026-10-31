.PHONY: run test shots clean
run:
	python3 run.py --roms $(ROMS)
test:
	python3 -m unittest discover -s tests -v
shots:
	SDL_VIDEODRIVER=dummy python3 run.py --render-frames 6 --render-out ./shots
clean:
	rm -rf shots __pycache__ rdvd/__pycache__ tests/__pycache__
