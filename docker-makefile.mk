# docker-makefile.mk

.PHONY: build run stop

build:
	docker-compose -f docker-compose-dev.yaml build

run:
	docker-compose -f docker-compose-dev.yaml up -d

stop:
	docker-compose -f docker-compose-dev.yaml down