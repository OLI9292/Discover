import os
import redis

redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379')
POOL = redis.ConnectionPool.from_url(redis_url)


def get_variable(variable_name):
    my_server = redis.Redis(connection_pool=POOL)
    response = my_server.get(variable_name)
    return response


def set_variable(variable_name, variable_value):
    my_server = redis.Redis(connection_pool=POOL)
    my_server.set(variable_name, variable_value)


def clear_variables():
    my_server = redis.Redis(connection_pool=POOL)
    my_server.flushall()


def instance():
    return redis.Redis(connection_pool=POOL)
