import ibis
import duckdb
import logging
import pandas as pd
import traceback as tb
from rpy2 import robjects
from sqlalchemy import text
from functools import partial

from prefect import task, flow

from flows.dataflow_ui_plugin.hooks import *
from flows.dataflow_ui_plugin.flowutils import *
from flows.dataflow_ui_plugin.types import JoinType

from shared_utils.types import UserType
from shared_utils.dao.DBDao import DBDao


class Node:
    def __init__(self, node):
        self.id = node["id"]
        self.type = node["type"]
        self.use_cache_db = False


class Flow(Node):
    def __init__(self, _node):
        self.graph = _node["graph"]
        self.executor_type = _node["executor_options"]["executor_type"]
        self.executor_host = _node["executor_options"]["executor_address"]["host"]
        self.executor_port = _node["executor_options"]["executor_address"]["port"]
        self.ssl = _node["executor_options"]["executor_address"]["ssl"]
        self.sorted_nodes = get_node_list(self.graph)


class Result:
    def __init__(self, error: bool, data, node: Node, task_run_context):
        self.error = error
        self.node = node
        self.task_run_id = str(task_run_context.get("id"))
        self.task_run_name = str(task_run_context.get("name"))
        self.flow_run_id = str(task_run_context.get("flow_run_id"))
        self.data = {
            "result": data,
            "error": self.error,
            "errorMessage": data if self.error else None,
            "nodeName": self.node.id
        }


class SqlNode(Node):
    """
    Execute queries on pandas dataframes using duckdb as backend.
    
    Attributes:
        tables: A dictionary mapping of a user input table name to a dataframe from an incoming node. 
        sql: The sql query to execute.
    """
    def __init__(self, _node):
        super().__init__(_node)
        self.tables = _node["tables"]
        self.sql = _node["sql"]
        
    def __exec_query(self, _input) -> pd.DataFrame:
        con = None
        try:
            # create temporary in-memory table and register input dfs as tables
            con = duckdb.connect()
            for table_name, input_node in self.tables.items():
                table_df = _input[input_node].data.get("result")
                con.register(table_name, table_df)
            result_df = con.execute(self.sql).fetch_df()
            return result_df
        except Exception as e:
            raise e
        finally:
            if con:
                con.close()
        
            
    def task(self, _input: dict[str, Result], task_run_context)  -> pd.DataFrame:
        try:
            result_df = self.__exec_query(_input)
            return Result(False,  result_df, self, task_run_context)
        except Exception as e:
            return Result(True, tb.format_exc(), self, task_run_context)

    def test(self, _input: dict[str, Result], task_run_context):
        return self.task(_input, task_run_context)


class PythonNode(Node):
    def __init__(self, _node):
        super().__init__(_node)
        self.source_code = _node["python_code"] + '\noutput = exec(myinput)'
        self.test_source_code = _node["python_code"]+'\noutput = test_exec(myinput)'
        
    def test(self, _input: dict[str, Result], task_run_context):
        params = {"myinput": _input, "output": {}}
        testcode = compile(self.test_source_code, '<string>', 'exec')
        e = exec(testcode, params)
        return params["output"]

    def task(self, _input: dict[str, Result], task_run_context):
        params = {"myinput": _input, "output": {}}
        try:
            code = compile(self.source_code, '<string>', 'exec')
            data = exec(code, params)
            return Result(False,  params["output"], self, task_run_context)
        except Exception as e:
            return Result(True, tb.format_exc(), self, task_run_context)


class RNode(Node):
    def __init__(self, _node):
        super().__init__(_node)
        self.r_code = ''''''+_node["r_code"]+''''''

    def test(self, _input: dict[str, Result], task_run_context):
        
        with robjects.conversion.localconverter(robjects.default_converter):
            r_inst = robjects.r(self.r_code)
            r_test_exec = robjects.globalenv['test_exec']
            global_params = {"r_test_exec": r_test_exec, "convert_R_to_py": convert_R_to_py,
                             "myinput": convert_py_to_R(_input), "output": {}}
            e = exec(
                f'output = convert_R_to_py(r_test_exec(myinput))', global_params)
        output = global_params["output"]
        return output

    def task(self, _input: dict[str, Result], task_run_context):
        try:
            
            with robjects.robjects.conversion.localconverter(robjects.default_converter):
                r_inst = robjects.r(self.r_code)
                r_exec = robjects.globalenv['exec']
                global_params = {"r_exec": r_exec, "convert_R_to_py": convert_R_to_py,
                                 "myinput": convert_py_to_R(_input), "output": {}}
                e = exec(f'output = convert_R_to_py(r_exec(myinput))',
                         global_params)
            output = global_params["output"]
            return Result(False,  output, self, task_run_context)
        except Exception as e:
            return Result(True, tb.format_exc(), self, task_run_context)


class CsvNode(Node):
    def __init__(self, _node):
        super().__init__(_node)
        self.file = _node["file"]
        self.name = _node["name"]
        self.delimiter = _node["delimiter"]
        self.names = _node["columns"]
        self.hasheader = _node["hasheader"]
        # self.types = _node["datatypes"]

    def _load_csv_into_dataframe(self) -> pd.DataFrame:
        if self.hasheader:
            # dtype=self.types
            df = pd.read_csv(self.file, delimiter=self.delimiter)

        else:
            df = pd.read_csv(self.file, 
                             header=None, 
                             names=self.names,
                             delimiter=self.delimiter)  # dtype=self.types
        return df


    def test(self, task_run_context):
        ddf = self._load_csv_into_dataframe()
        return ddf

    def task(self, task_run_context) -> Result:
        try:
            ddf = self._load_csv_into_dataframe()
            return Result(False,  ddf, self, task_run_context)
        except Exception as e:
            return Result(True, tb.format_exc(), self, task_run_context)


class DbWriter(Node):
    def __init__(self, _node):
        super().__init__(_node)
        self.tablename = _node["dbtablename"]
        self.database = _node["database"] 
        self.dataframe = _node["dataframe"]
        self.use_cache_db = _node["use_cache_db"]

    def test(self, _input: dict[str, Result], task_run_context):
        return False

    def task(self, _input: dict[str, Result], task_run_context):
        input_element = _input
        
        admin_user = UserType.ADMIN_USER
        dbutils = DBUtils(use_cache_db=self.use_cache_db, 
                          database_code=self.database)
        dbconn = dbutils.create_database_engine(user_type=admin_user)
        try:
            for path in self.dataframe:
                input_element = input_element[path].data
            result = input_element.to_sql(
                self.tablename, dbconn, if_exists='replace')
            return Result(False,  result, self, task_run_context)
        except Exception as e:
            return Result(True, tb.format_exc(), self, task_run_context)



class SqlQueryNode(Node):
    """
    Execute queries on database with read user connection.
    
    Attributes:
        params: A dictionary mapping parameters in sql expression to input nodes.
        sqlquery: The sql query to execute.
        testsqlquery: The test sql query to execute.
        is_select: To flag if the sqlquery/testsqlquery is a select statement.
        database: The database code.
        schema: The name of a default schema to use.
        use_cache_db: Boolean flag to use cache db. 
    """
    def __init__(self, _node):
        super().__init__(_node)
        self.sqlquery = _node["sqlquery"]
        if "testsqlquery" in _node:
            self.testsqlquery = _node["testsqlquery"]
        else:
            self.testsqlquery = _node["sqlquery"]
        self.params = {}
        self._is_select = _node["is_select"]
        if "params" in _node:
            self.params = _node["params"]
        self.database = _node["database"]
        self.schema = _node["schema"]
        self.use_cache_db = _node["use_cache_db"]


    def __compile_with_params(self, sqlquery: str, bind_params: dict) -> str:
        # Use sqlalchemy as ibis does not support bound parameters with raw sql
        if not bind_params:
            return sqlquery
        raw_sql = text(sqlquery).bindparams(**bind_params).compile(compile_kwargs={"literal_binds": True})
        return str(raw_sql)

    def _exec(self, _input: dict[str, Result], sqlquery: str) -> pd.DataFrame | None:
        con = None
        try:
            tenant_configs = DBDao(use_cache_db=self.use_cache_db, 
                                   database_code=self.database, 
                                   schema_name=self.schema).tenant_configs
            con = ibis.postgres.connect(database=self.database,
                                        host=tenant_configs.host,
                                        user=tenant_configs.readUser,
                                        password=tenant_configs.readPassword.get_secret_value())
            retrieved_params = {param: _input[node].data.get("result") 
                                for param, node in self.params.items()}
            
            compiled_query = self.__compile_with_params(sqlquery, retrieved_params)
            
            result = con.sql(compiled_query)
            if self._is_select:
                return result.to_pandas()
            return
        except Exception as e:
            raise e

    def test(self, _input: dict[str, Result], task_run_context):
        try:
            df = self._exec(_input, self.testsqlquery)
            return Result(False,  df, self, task_run_context)
        except Exception as e:
            return Result(True, tb.format_exc(), self, task_run_context)

    def task(self, _input: dict[str, Result], task_run_context):
        try:
            df = self._exec(_input, self.sqlquery)
            return Result(False,  df, self, task_run_context)
        except Exception as e:
            return Result(True, tb.format_exc(), self, task_run_context)


# To do: link up with JSON from UI
class DataMappingNode(Node):
    """
    Map fields from multiple source dataframes to target tables.
    
    Attributes:
        source_node_dfs: A dictionary mapping each source table to a input node containing a source dataframe.
        table_joins: A dictionary specifying how a left table should be joined to a right table.
        data_mapping: A dictionary mapping the columns from a source table to a columns of a target table. 
    """
    def __init__(self, _node):
        super().__init__(_node)
        self.data_mapping = _node["data_mapping"]
        self.table_joins = _node["table_joins"]
        self.source_node_dfs = _node["tables"]

    def __create_target_table(self, _input: dict[str, Result], target_table: str) -> pd.DataFrame:
        con = None
        try:
            # create temporary in-memory table and register input dfs as tables
            con = ibis.duckdb.connect()
            ibis_mem_tables = {}
            source_table_list = [mapping["input_table"] for mapping in self.data_mapping 
                                 if mapping["output_table"]==target_table]
            for source_table in source_table_list:
                source_node = self.source_node_dfs.get(source_table)
                source_table_df = _input[source_node].data.get("result")
                ibis_mem_tables[source_table] = con.register(table_name=source_table, source=source_table_df)
            
            # create a base select statement by joining all input tables
            base_expr = self.__create_joined_tables_expression(target_table, ibis_mem_tables)
            
            # create a select statement with mapped field inputs
            select_expr = self.__create_select_expression(target_table, base_expr, ibis_mem_tables)

            output_df = select_expr.execute()
            return output_df
        
        except Exception as e:
            raise e
        finally:
            if con:
                con.close()

    def __order_joins(self, target_table_joins: list) -> list:
        sorted_joins = []
        
        left_tables = set(x["left_table_name"] for x in target_table_joins)
        right_tables = set(x["right_table_name"] for x in target_table_joins)
        leftmost_table = (left_tables - right_tables).pop()
        current_table = leftmost_table
        tables_to_visit = set()

        # while left_nodes != {} and current_table is not None:
        while current_table is not None:
            if current_table not in left_tables:
                pass
            else:
                left_tables.remove(current_table)
                for join in target_table_joins:
                    if join["left_table_name"] == current_table:
                        tables_to_visit.add(join["right_table_name"])
                        sorted_joins.append(join)

            if len(tables_to_visit) == 0:
                current_table = None
            else:
                current_table = tables_to_visit.pop()
            
        return sorted_joins


    def __create_joined_tables_expression(self, target_table: str, ibis_mem_tables: dict):
        target_table_joins = [config for config in self.table_join_config_list if config["target_table"]==target_table]
        ordered_joins = self.__order_joins(target_table_joins)

        # chain joins
        # start with left most table and join from left to right
        join_expr = ibis_mem_tables.get(ordered_joins[0]["left_table_name"])

        for config in ordered_joins:
            left_table = ibis_mem_tables.get(config["left_table_name"])
            right_table = ibis_mem_tables.get(config["right_table_name"])
            left_table_join_col = config["left_table_join_on"]
            right_table_join_col = config["right_table_join_on"]
            
            # Apply join on left table and right table
            match config.join_type:
                case JoinType.LEFT_OUTER:
                    join_expr = join_expr.left_join(right_table, left_table[left_table_join_col]==right_table[right_table_join_col])
                case JoinType.FULL_OUTER:
                    join_expr = join_expr.outer_join(right_table, left_table[left_table_join_col]==right_table[right_table_join_col])
                case _:
                    join_expr = join_expr.inner_join(right_table, left_table[left_table_join_col]==right_table[right_table_join_col])

        return join_expr


    def __create_select_expression(self, target_table: str, base_expr, ibis_mem_tables: dict):
        selected_columns = []
        for mapping in self.data_mapping:
            if mapping["output_table"] == target_table:
                tbl_to_select = ibis_mem_tables.get(mapping["input_table"])
                for col in mapping["fields"]:
                    selected_columns.append(tbl_to_select[col["source_field"]].name(col["target_field"]))
                    
        select_expr = base_expr.select(selected_columns)
        
        return select_expr

    def test(self, _input: dict[str, Result], task_run_context):
        return self.task(_input, task_run_context)

    def task(self, _input: dict[str, Result], task_run_context):  # executes the retrieved sql query
        try:
            target_table_dfs = {}
            target_table_list = set(mapping["output_table"] for mapping in self.data_mapping)
            # Todo: Confirm if
            for target_table in target_table_list:
                target_table_dfs[target_table] = self.__create_target_table(_input, target_table)
        except Exception as e:
            return Result(True, tb.format_exc(), self, task_run_context)
        else:
            return Result(False, target_table_dfs, self, task_run_context)


@flow(name="generate-nodes",
      flow_run_name="generate-nodes-flowrun",
      log_prints=True)
def generate_nodes_flow(graph, sorted_nodes):
    for nodename in sorted_nodes:
        node = graph["nodes"][nodename]
        nodetype = node["type"]

        # check if node is a subflow
        if nodetype == "subflow":
            subflow_obj = Flow(node)
            graph["nodes"][nodename]["nodeobj"] = subflow_obj
            for subflow_nodename in subflow_obj.sorted_nodes:
                subflow_nodegraph = subflow_obj.graph["nodes"][subflow_nodename]
                subflow_nodetype = subflow_nodegraph["type"]
                # create task run to generate node obj for each subflow node
                subflow_node_obj = generate_node_task(
                    subflow_nodename, subflow_nodegraph, subflow_nodetype)
                graph["nodes"][nodename]["graph"]["nodes"][subflow_nodename]["nodeobj"] = subflow_node_obj
        else:
            node_task_generation_wo = generate_node_task.with_options(
                on_completion=[partial(
                    node_task_generation_hook, **dict(nodename=nodename, nodetype=nodetype))],
                on_failure=[partial(node_task_generation_hook,
                                    **dict(nodename=nodename, nodetype=nodetype))]
            )

            nodeobj = node_task_generation_wo(nodename, node, nodetype)

            graph["nodes"][nodename]["nodeobj"] = nodeobj
    return graph


@task(task_run_name="generate-node-taskrun-{nodename}",
      log_prints=True
      )
def generate_node_task(nodename, node, nodetype):
    nodeobj = None
    # TODO: nodetype to make global variable
    match nodetype:
        case "csv_node":
            nodeobj = CsvNode(node)
        case "sql_node":
            nodeobj = SqlNode(node)
        case "python_node":
            nodeobj = PythonNode(node)
        case "r_node":
            nodeobj = RNode(node)
        case "db_writer_node":
            nodeobj = DbWriter(node)
        case "sql_query_node":
            nodeobj = SqlQueryNode(node)
        case "data_mapping_node":
            nodeobj = DataMappingNode(node)
        case _:
            logging.error("ERR: Unknown Node "+node["type"])
            logging.error(tb.StackSummary())
    return nodeobj


def serialize_result_to_json(result: Result):
    return serialize_to_json(result.data)
