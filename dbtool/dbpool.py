# -*-coding:utf-8-*-
import logging

import pymysql
from dbutils.persistent_db import PersistentDB


def escape_string(val):
    """转义字符串"""
    if not val:
        return ''
    return pymysql.converters.escape_string(val)


def setup_logger(name):
    """创建日志记录器"""
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(formatter)
        logger.addHandler(stream_handler)
    return logger


def mysql_decorator(original_method):
    """mysql重试装饰器"""

    def retry_method(self, *args, **kwargs):
        retry_count = 0
        while retry_count < 3:
            try:
                result = original_method(self, *args, **kwargs)
                return result
            except pymysql.Error as e:
                if self.log_enabled:
                    self.logger.error(f"Pymysql error: {str(e)}")
                if e.args[0] in (2006, 2013):
                    retry_count += 1
                    if retry_count >= 3:
                        raise e
                    else:
                        if self.log_enabled:
                            self.logger.info(f"Retry count: {retry_count}")
                        continue
                else:
                    raise e

    # 返回包装方法
    return retry_method


class MysqlBase:

    def __init__(self, logger_name, log_enabled):
        self.log_enabled = log_enabled
        self.in_transaction = False  # 添加in_transaction属性
        if self.log_enabled:
            self.logger = setup_logger(logger_name)

    def need_close(self):
        """是否需要关闭连接"""
        if self.get_class_name() == "MysqlClass":
            return False

        return True

    def get_class_name(self):
        """获取类名"""
        return self.__class__.__name__

    def get_connection(self) -> pymysql.connections.Connection:
        pass

    @mysql_decorator
    def fetchall(self, sql, args=None):
        """执行查询语句，并记录日志"""
        if self.log_enabled:
            self.logger.info(f"Executing SQL fetchall: {sql} with args: {args}")

        connection = self.get_connection()
        cur = connection.cursor()
        cur.execute(sql, args)
        result = cur.fetchall()

        if self.need_close():
            cur.close()
            connection.close()
        if self.log_enabled:
            self.logger.info(f"Query result len: {len(result)}")
        return result

    @mysql_decorator
    def fetchone(self, sql, args=None):
        """执行查询单个，并记录日志"""
        if self.log_enabled:
            self.logger.info(f"Executing SQL fetchone: {sql} with args: {args}")

        connection = self.get_connection()
        cur = connection.cursor()
        cur.execute(sql, args)
        result = cur.fetchone()

        if self.need_close():
            cur.close()
            connection.close()

        return result

    def execute(self, sql, args=None, get_last_row_id=False):
        """执行单次更新或插入语句，返回受影响行数，并记录日志"""
        if self.log_enabled:
            self.logger.info(f"Executing SQL statement: {sql} with args: {args}")

        connection = self.get_connection()
        cur = connection.cursor()
        cur.execute(sql, args)
        exec_result = cur.rowcount
        if self.log_enabled:
            self.logger.info(f"Affected rows: {cur.rowcount}")
        if get_last_row_id:
            if self.log_enabled:
                self.logger.info(f"Last row_id: {cur.lastrowid}")
            exec_result = cur.lastrowid

        if not self.in_transaction:  # 不在事务中自动提交
            connection.commit()

        if self.need_close() and not self.in_transaction:
            cur.close()
            connection.close()

        return exec_result

    def get_last_row_id(self):
        """ 执行单次更新或插入语句，返回最后的id，并记录日志"""
        if self.log_enabled:
            self.logger.info(f"get last row id")

        connection = self.get_connection()
        cur = connection.cursor()
        cur.execute('SELECT LAST_INSERT_ID() as last_row_id;')
        result = cur.fetchone()
        last_row_id = result['last_row_id']

        if self.need_close():
            cur.close()
            connection.close()
        if self.log_enabled:
            self.logger.info(f"Last row id: {last_row_id}")
        return last_row_id

    def executemany(self, sql, args=None):
        """批量執行更新或插入语句，并记录日志,返回受影响的行数"""
        if self.log_enabled:
            self.logger.info(f"Executing ManySQL statement: {sql} with args: {args}")

        connection = self.get_connection()
        cur = connection.cursor()
        cur.executemany(sql, args)
        affected_rows = cur.rowcount

        if not self.in_transaction:  # 不在事务中自动提交
            connection.commit()

        if self.need_close() and not self.in_transaction:
            cur.close()
            connection.close()

        if self.log_enabled:
            self.logger.info(f"Affected rows: {affected_rows}")
        return affected_rows

    def transaction(self):
        """创建事务对象"""
        return MysqlTransaction(self)


class MysqlFactor(object):

    @staticmethod
    def create(db_config, pool=False, log_enabled=True, max_usage=5) -> MysqlBase:
        if pool:
            return MysqlPool(db_config, log_enabled, max_usage)
        else:
            return MysqlClass(db_config, log_enabled)


class MysqlClass(MysqlBase):
    def __init__(self, db_config, log_enabled):
        """初始化数据库连接池和日志记录器"""
        super().__init__(db_config['sql_user'], log_enabled)
        config = {
            'host': db_config['sql_host'],
            'user': db_config['sql_user'],
            'password': db_config['sql_pass'],
            'port': db_config['sql_port'],
            'charset': 'utf8',
            'cursorclass': pymysql.cursors.DictCursor,
            'autocommit': False,
            'database': db_config['database'],
        }

        self.connection = pymysql.connect(**config)

    def get_connection(self) -> pymysql.connections.Connection:
        return self.connection


class MysqlPool(MysqlBase):
    _instances = {}

    def __new__(cls, db_config, log_enabled, max_usage):
        """单例模式，根据db_config的不同，返回不同的实例"""
        key = tuple(sorted(db_config.items()))
        if key not in cls._instances:
            cls._instances[key] = super().__new__(cls)
        return cls._instances[key]

    def __init__(self, db_config, log_enabled, max_usage):
        """初始化数据库连接池和日志记录器"""
        super().__init__(db_config['sql_user'], log_enabled)
        config = {
            'host': db_config['sql_host'],
            'user': db_config['sql_user'],
            'password': db_config['sql_pass'],
            'port': db_config['sql_port'],
            'charset': 'utf8',
            'cursorclass': pymysql.cursors.DictCursor,
            'autocommit': False,
            'maxusage': max_usage,
        }
        if not hasattr(self, "pool"):
            self.pool = PersistentDB(pymysql, **config)

    def get_connection(self) -> pymysql.connections.Connection:
        return self.pool.connection()


class MysqlTransaction:
    def __init__(self, mysql_instance: MysqlBase):
        self._should_commit = True
        self.mysql_instance = mysql_instance
        self.connection = None
        self.used_with = False
        self.cur = None

    def __enter__(self):
        self.connection = self.mysql_instance.get_connection()
        self.cur = self.connection.cursor()
        self.connection.begin()
        self.mysql_instance.in_transaction = True  # 进入事务时将in_transaction设置为True
        self.used_with = True
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None or exc_val or not self._should_commit:
            self.connection.rollback()
        else:
            self.connection.commit()
        self.mysql_instance.in_transaction = False  # 退出事务时将in_transaction设置为False
        if self.mysql_instance.need_close():
            self.cur.close()
            self.connection.close()

    def execute_transaction(self, transaction_callable, *args, **kwargs):
        """
        执行事务，并根据闭包的返回值决定是否提交或回滚事务。
        闭包的签名为：def transaction_callable(transaction: MysqlTransaction) -> Union[bool, Exception]
        """
        if not self.used_with:  # 如果标志为False，表示没有使用with语句
            raise Exception("MysqlTransaction must be used with a 'with' statement")

        self._should_commit = True  # 默认应该提交事务

        try:
            result = transaction_callable(self, *args, **kwargs)
        except Exception as e:
            self._should_commit = False  # 出错时回滚事务
            raise e

        if result is False:
            self._should_commit = False  # 返回False时回滚事务

        return result
