import unittest

from wytool.Config.public import PublicConfig

from dbpool import MysqlPool


class MysqlPoolTestCase(unittest.TestCase):
    def setUp(self):
        # 创建 MysqlPool 实例
        self._instances = MysqlPool(PublicConfig.db)
        self._instances.execute("DELETE FROM resource.keyword_news_temp WHERE id > 0")

    def test_fetchall(self):
        insert_sql = "INSERT INTO resource.keyword_news_temp (create_time, content, add_user, tmpl_type) VALUES (%s, %s, %s, %s)"
        self._instances.executemany(insert_sql, [(1625501234, "Sample content", "user1", 0), (1625501234, "Another content", "user2", 0)])

        # 调用被测试的方法
        result = self._instances.fetchall("SELECT content FROM resource.keyword_news_temp")

        # 断言结果是否符合预期
        self.assertEqual(result, [
            {'content': 'Sample content'},
            {'content': 'Another content'}
        ])

    def test_get_last_row_id(self):
        # 模拟执行插入语句并返回最后的 id
        insert_sql = "INSERT INTO resource.keyword_news_temp (create_time, content, add_user, tmpl_type) VALUES (%s, %s, %s, %s)"
        last_id = self._instances.execute(insert_sql, (1625501234, "Sample content", "user1", 0), get_last_row_id=True)

        # 调用被测试的方法
        last_row_id = self._instances.get_last_row_id()

        # 断言结果是否符合预期
        self.assertNotEqual(last_row_id, 0)
        self.assertEqual(last_row_id, last_id)

    def test_execute(self):
        # 调用被测试的方法
        affected_rows = self._instances.execute(
            "INSERT INTO resource.keyword_news_temp (create_time, content, add_user, tmpl_type) VALUES (%s, %s, %s, %s)",
            (1625501234, "Sample content", "user2", 0)
        )

        # 断言结果是否符合预期
        self.assertEqual(affected_rows, 1)

    def test_transaction(self):
        # 模拟执行事务并返回 True
        def mock_transaction_callable(transaction):
            return True

        # 创建 MysqlTransaction 实例
        transaction = self._instances.transaction()

        # 调用被测试的方法
        result = transaction.execute_transaction(mock_transaction_callable)

        # 断言结果是否符合预期
        self.assertTrue(result)

    def test_transaction_with_exception(self):
        # 模拟执行事务并抛出异常
        def mock_transaction_callable(transaction):
            raise Exception("Some error occurred")

        # 创建 MysqlTransaction 实例
        transaction = self._instances.transaction()

        # 调用被测试的方法并捕获异常
        with self.assertRaises(Exception):
            transaction.execute_transaction(mock_transaction_callable)


if __name__ == '__main__':
    unittest.main()
