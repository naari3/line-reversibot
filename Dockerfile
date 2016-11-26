FROM ubuntu:16.04
MAINTAINER naari_
RUN sed -i'~' -E "s@http://(..\.)?(archive|security)\.ubuntu\.com/ubuntu@http://ftp.jaist.ac.jp/pub/Linux/ubuntu@g" /etc/apt/sources.list

# COPY initdb.sql /docker-entrypoint-initdb.d/

RUN apt-get update &&  apt-get -y install\
  build-essential libsqlite3-dev\
  libreadline6-dev libgdbm-dev zlib1g-dev libbz2-dev\
  sqlite3 tk-dev zip libssl-dev gfortran liblapack-dev\
  wget  libpq-dev git language-pack-ja-base language-pack-ja\
  postgresql nginx supervisor
RUN locale-gen ja_JP.UTF-8
ENV LANG ja_JP.UTF-8
ENV LANGUAGE ja_JP:ja
ENV LC_ALL ja_JP.UTF-8

ENV SOURCE_TARBALL 'https://python.org/ftp/python/3.5.2/Python-3.5.2.tgz'
RUN wget $SOURCE_TARBALL
RUN tar axvf ./Python-3.5.2.tgz
WORKDIR /Python-3.5.2/
RUN LDFLAGS="-L/usr/lib/x86_64-linux-gnu" ./configure --with-ensurepip --with-zlib
RUN make
RUN make install

# reversi
RUN pip3 install --upgrade pip
RUN git clone https://github.com/naari3/line-reversibot.git /app/
COPY ./auth.yml /app/
WORKDIR /app/
RUN pip3 install -r requirements.txt
# ENV DATABASE_URL postgres://docker:docker@127.0.0.1:5432/reversi_db # supervisorのconfに書かないとだめ

# postgres
RUN echo "listen_addresses = '*'" >> /etc/postgresql/9.5/main/postgresql.conf
COPY ./Docker/postgresql/pg_hba.conf /etc/postgresql/9.5/main/pg_hba.conf
  # psql --command "CREATE USER docker WITH SUPERUSER PASSWORD 'docker';"
  # psql --command "CREATE DATABASE docker WITH OWNER docker TEMPLATE template0 ENCODING 'UTF8';"
COPY ./Docker/postgresql/initdb.sql /

# nginx
COPY ./Docker/nginx/nginx.conf /etc/nginx/
COPY ./Docker/nginx/reversi.conf /etc/nginx/conf.d/

# supervisor
COPY ./Docker/supervisor/reversi-bot.conf /etc/supervisor/conf.d/

# gunicorn
COPY ./Docker/gunicorn/gunicorn-config.py /app/

# init
COPY ./Docker/init.sh /
CMD ["/bin/bash", "/init.sh"]
# CMD ["/usr/local/bin/python3", "reversi-bot.py"] # CMDは複数実行できないらしい

# ln $OUT_PREFIX/bin/python3 $OUT_PREFIX/bin/python
EXPOSE 443:443
EXPOSE 80:80
