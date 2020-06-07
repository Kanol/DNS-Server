import pickle
import socket
import signal
import sys
from select import select
from datetime import timedelta, datetime

from dnslib import DNSError, DNSRecord

forward_server = "8.8.8.8"

CACHE_FILE_NAME = "dnscache.pickle"


# Класс для хранения записей в кэше
class Record:
    def __init__(self, resource_record, create_time):
        self.resource_record = resource_record
        self.create_time = create_time


# Загрузка кэша из файла
def load_cache_from_disk(filename):
    cache = {}
    try:
        with open(filename, "rb") as file:
            cache = pickle.load(file)
            print("Cache loaded successfully")
    except:
        print("Cache not found")
    return cache


# Сохранения кэша в файл
def save_cache_to_disk(cache, filename):
    try:
        with open(filename, "wb") as file:
            print("Saving cache...")
            pickle.dump(cache, file)
            print("Cache saved successfully")
    except BaseException:
        print("Cache saving error")


# Удаление старых записей
def clear_old_cache(cache):
    for key in list(cache.keys()):
        record = cache[key]
        if datetime.now() - record.create_time > timedelta(seconds=record.resource_record.ttl):
            print("Deleting old cache record:", record.resource_record)
            del cache[key]


# Кэширование записи
def cache_record(rr, date_time, cache):
    k = (str(rr.rname).lower(), rr.rtype)
    cache[k] = Record(rr, date_time)


# Кеширование записей
def cache_records(dns_record, cache):
    for record in dns_record.rr + dns_record.auth + dns_record.ar:
        print(record)
        date_time = datetime.now()
        cache_record(record, date_time, cache)


# Поиск записи в кэше
def find_record_in_cache(dns_record, cache):
    key = (str(dns_record.q.qname).lower(), dns_record.q.qtype)
    if key in cache:
        print("Record founded in cache")
        reply = dns_record.reply()
        reply.rr = [cache[key].resource_record]
        return reply


# Основной цикл
def main():
    print("Starting DNS Server")
    print("Loading cache from disk...")
    global cache
    cache = load_cache_from_disk(CACHE_FILE_NAME)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("localhost", 53))
    while True:
        data_in_socket, _, _ = select([sock], [], [], 1)
        if not data_in_socket:
            continue
        conn, addr = sock.recvfrom(2048)
        clear_old_cache(cache)
        try:
            dns_record = DNSRecord.parse(conn)
        except DNSError:
            print("Can't parse DNS record")
            continue
        cache_records(dns_record, cache)
        if not dns_record.header.qr:
            response = find_record_in_cache(dns_record, cache)
            if response:
                response = response.pack()
            else:
                try:
                    response = dns_record.send(forward_server)
                    cache_records(DNSRecord.parse(response), cache)
                except (OSError, DNSError):
                    print("Server " + forward_server + "unavailable")
            sock.sendto(response, addr)
        save_cache_to_disk(cache, CACHE_FILE_NAME)


def stop(signal, frame):
    clear_old_cache(cache)
    save_cache_to_disk(cache, CACHE_FILE_NAME)
    print('Server stoped')
    sys.exit(0)


if __name__ == '__main__':
    signal.signal(signal.SIGINT, stop)
    main()
