CREATE USER docker WITH SUPERUSER PASSWORD 'docker';
drop database if exists reversi_db;
CREATE DATABASE docker WITH OWNER docker TEMPLATE template0 ENCODING 'UTF8';
create database reversi_db with owner = docker;
\c reversi_db docker
drop table if exists reversi;
create table reversi (
  user_id char(33) primary key,
  data text
);
drop table if exists reversi_result;
create table reversi_result (
  user_id char(33) primary key,
  win int,
  lose int,
  draw int
);
