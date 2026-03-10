import redis

r = redis.Redis(host='localhost', port=6379, db=4)

pubsub = r.pubsub()
pubsub.psubscribe('__keyspace@4__:*')

for message in pubsub.listen():
    print(message)