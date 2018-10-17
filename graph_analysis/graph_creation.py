import json
import pandas as pd
import networkx as nx

from itertools import combinations

from .utils import (create_column_values_under,
                    create_column_values_space,
                    create_column_values_singleton,
                    match_changes,)
from .graph_objects import PropertyDiGraph


class Manager(object):
    """Class for raw data input and distribution to other classes.

    The Manager takes in a list of n excel filepaths and a single json_path.
    The first Excel file in the excel_path input variable is assumed to be the
    baseline to which all subsequent excel paths will be compared as ancestors.
    A single json_path is taken because all of the input excel files are
    assumed to be of the same type and thus to correspond to the same set of
    data keys.

    Attribtues
    ----------
    excel_path : list
        list of paths to Excel Files.

    json_path : string
        string representing a path to a *.json file that is the key to decoding
        the Excel inputs into MagicDraw compatiable outputs.

    json_data : dictionary
        The json data associated with the json_path.

    translator : MDTranslator
        The MDTranslator object which can be passed to classes that require its
        functionality.

    evaluators : Evaluator
        list of the Evaluators created for each Excel file in the excel_path.
        len(evaluators) == len(excel_path)
    """

    def __init__(self, excel_path=[], json_path=None):
        self.excel_path = excel_path
        self.json_path = json_path
        self.json_data = None
        self.get_json_data()
        self.translator = MDTranslator(json_data=self.json_data)
        self.evaluators = []
        self.create_evaluators()

    def get_json_data(self):
        with open(self.json_path) as f:
            self.json_data = json.load(f)

    def create_evaluators(self):
        for excel_file in self.excel_path:
            self.evaluators.append(
                Evaluator(excel_file=excel_file,
                          translator=self.translator))

    def get_pattern_graph_diff(self):
        evaluator_dict = {index: evaluator for evaluator, index in enumerate(
            self.evaluators
        )}
        evaluator_change_dict = {}

        for pair in combinations(self.evaluators, 2):
            eval_1_e_dict = pair[0].prop_di_graph.edge_dict
            eval_2_e_dict = pair[1].prop_di_graph.edge_dict

            edge_set_one = pair[0].edge_set  # get Parent edge set
            edge_set_two = pair[1].edge_set  # get the ancestor edge set

            # remove common edges
            # have to do this with named edges.
            eval_one_unmatched = list(edge_set_one.difference(edge_set_two))
            eval_two_unmatched = list(edge_set_two.difference(edge_set_one))

            eval_one_unmatch_map = dict((edge.edge_attribute, list())
                                        for edge in eval_one_unmatched)
            eval_two_unmatch_map = dict((edge.edge_attribute, list())
                                        for edge in eval_two_unmatched)

            # possible optimization is to append the edge
            for edge in eval_one_unmatched:
                eval_one_unmatch_map[edge.edge_attribute].append(
                    edge)
            for edge in eval_two_unmatched:
                eval_two_unmatch_map[edge.edge_attribute].append(
                    edge)

            eval_one_unmatch_pref = {}
            eval_two_unmatch_pref = {}
            for edge in eval_one_unmatched:
                if edge.edge_attribute not in eval_two_unmatch_map.keys():
                    eval_one_unmatch_pref[edge] = []
                else:
                    eval_one_unmatch_pref[edge] = eval_two_unmatch_map[
                        edge.edge_attribute]
            for edge in eval_two_unmatched:
                if edge.edge_attribute not in eval_one_unmatch_map.keys():
                    eval_two_unmatch_pref[edge] = []
                else:
                    eval_two_unmatch_pref[edge] = eval_one_unmatch_map[
                        edge.edge_attribute]

            eval_one_matches = match_changes(change_dict=eval_one_unmatch_pref)
            eval_two_matches = match_changes(change_dict=eval_two_unmatch_pref)

            for no_match in eval_one_matches['no matches']:
                eval_two_matches['no matches'].append(no_match)

            key = '{0} and {1}'.format(evaluator_dict[pair[0]],
                                       evaluator_dict[pair[1]])
            evaluator_change_dict.update({key: eval_two_matches})

        return evaluator_change_dict


class Evaluator(object):
    """Class for creating the PropertyDiGraph from the Excel data with the help
    of the MDTranslator.

    Evaluator produces a Pandas DataFrame from the Excel path provided by the
    Manager. The Evaluator then updates the DataFrame with column headers
    compliant with MagidDraw and infers required columns from the data stored
    in the MDTranslator. With the filled out DataFrame the Evaluator produces
    the PropertyDiGraph.

    Parameters
    ----------
    excel_file : string
        String to an Excel File

    translator : MDTranslator
        MDTranslator object that holds the data from the *.json file
        associated with this type of Excel File.

    Attributes
    ----------
    df : Pandas DataFrame
        DataFrame constructed from reading the Excel File.

    prop_di_graph : PropertyDiGraph
        PropertyDiGraph constructed from the data in the df.

    root_node_attr_columns : set
        Set of column names in the initial read of the Excel file that do not
        appear as Vertices in the MDTranslator definition of the expected
        Vertices. The columns collected here will later be associated to the
        corresponding root node as additional attributes.

    Properties
    ----------
    named_vertex_set : set
        Returns the named vertex set from the PropertyDiGraph.

    vertex_set : set
        Returns the vertex set from the PropertyDiGraph
    """

    # TODO: Consider moving function calls into init since they should be run
    # then
    def __init__(self, excel_file=None, translator=None):
        self.translator = translator
        self.df = pd.read_excel(excel_file)
        self.df.dropna(how='all', inplace=True)
        self.prop_di_graph = None
        self.root_node_attr_columns = set()

    # def validate_cols_keys_map(self):
    #     df_cols = set(self.df.columns)
    #     data_keys = set(translator.get_cols_to_nav_map())
    #     try:
    #         df_cols == data_keys

    def rename_df_columns(self):
        """Returns renamed DataFrame columns from their Excel name to their
        MagicDraw name. Any columns in the Excel DataFrame that are not in the
        json are recorded as attribute columns.
        """
        for column in self.df.columns:
            try:
                new_column_name = self.translator.get_col_uml_names(
                    column=column)
                self.df.rename(columns={column: new_column_name}, inplace=True)
            except KeyError:
                # We continue because these columns are additional data
                # that we will associate to the Vertex as attrs.
                self.root_node_attr_columns.add(column)

    def add_missing_columns(self):
        """Adds the missing column to the dataframe. These columns are ones
        required to fillout the pattern in the MDTranslator that were not
        specified by the user. The MDTranslator provides a template for naming
        these inferred columns.

        Notes
        -----
        Stepping through the function, first a list of column names that
        appear in the JSON but not the Excel are compiled by computing the
        difference between the expected column set from the Translator and the
        initial dataframe columns. Then those columns are sorted by length
        to ensure that longer column names constructed of multiple shorter
        columns do not fail when searching the dataframe.
            e.g. Suppose we need to construct the column
            A_composite owner_component. Sorting by length ensures that
            columns_to_create = ['component', 'composite owner',
            'A_composite owner_component']
        Then for each column name in columns to create, the column name is
        checked for particular string properties and the inferred column values
        are determined based on the desired column name.

        """
        # from a collection of vertex pairs, create all of the columns for
        # for which data is required but not present in the excel.
        columns_to_create = list(set(
            self.translator.get_pattern_graph()).difference(
            set(self.df.columns)))
        # TODO: Weak solution to the creation order problem.
        columns_to_create = sorted(columns_to_create, key=len)

        under = '_'
        space = ' '
        dash = '-'

        for col in columns_to_create:
            if under in col:
                if dash in col:
                    col_data_vals = col.split(sep=under)
                    suffix = col_data_vals[-1].split(sep=dash)
                    first_node_data = self.df.loc[:, col_data_vals[1]]
                    second_node_data = self.df.loc[:, suffix[0]]
                    suff = dash + suffix[-1]
                    self.df[col] = create_column_values_under(
                        prefix=col_data_vals[0],
                        first_node_data=first_node_data,
                        second_node_data=second_node_data,
                        suffix=suff
                    )
                else:
                    col_data_vals = col.split(sep=under)
                    first_node_data = self.df.loc[:, col_data_vals[1]]
                    second_node_data = self.df.loc[:, col_data_vals[2]]
                    self.df[col] = create_column_values_under(
                        prefix=col_data_vals[0],
                        first_node_data=first_node_data,
                        second_node_data=second_node_data,
                        suffix=''
                    )
            elif space in col:
                col_data_vals = col.split(sep=space)
                root_col_name = self.translator.get_root_node()
                # TODO: Update this with rule from Bjorn.
                first_node_data = self.df.iloc[:, 0]
                second_node_data = self.df.loc[:, root_col_name]
                self.df[col] = create_column_values_space(
                    first_node_data=first_node_data,
                    second_node_data=second_node_data
                )
            else:
                col_data_vals = col
                root_col_name = self.translator.get_root_node()
                first_node_data = self.df.loc[:, root_col_name]
                second_node_data = [
                    col for count in range(len(first_node_data))]
                self.df[col] = create_column_values_singleton(
                    first_node_data=first_node_data,
                    second_node_data=second_node_data
                )

    def to_property_di_graph(self):
        """Creates a PropertyDiGraph from the completely filled out dataframe.
        To achieve this, we loop over the Pattern Graph Edges defined in the
        JSON and take each pair of columns and the edge type as a source,
        target pair with the edge attribute corresponding to the edge type
        defined in the JSON.
        """
        self.prop_di_graph = PropertyDiGraph(
            root_attr_columns=self.root_node_attr_columns
        )
        for index, pair in enumerate(
                self.translator.get_pattern_graph_edges()):
            edge_type = self.translator.get_edge_type(index=index)
            self.df[edge_type] = edge_type
            df_temp = self.df[[pair[0], pair[1], edge_type]]
            GraphTemp = nx.DiGraph()
            GraphTemp = nx.from_pandas_edgelist(
                df=df_temp, source=pair[0],
                target=pair[1], edge_attr=edge_type,
                create_using=GraphTemp)
            self.prop_di_graph.add_nodes_from(GraphTemp)
            self.prop_di_graph.add_edges_from(GraphTemp.edges,
                                              edge_attribute=edge_type)

    @property
    def named_vertex_set(self):
        return self.prop_di_graph.get_vertex_set_named(df=self.df)

    @property
    def vertex_set(self):
        return self.prop_di_graph.vertex_set

    @property
    def named_edge_set(self):
        return self.prop_di_graph.named_edge_set

    @property
    def edge_set(self):
        return self.prop_di_graph.edge_set


class MDTranslator(object):
    """
    Class to serve as the Rosetta Stone for taking column headers from the
    Excel input to the MagicDraw compatible output. More specifically, this
    class provides access to data in the JSON file allowing the Evaluator to
    determine which columns are required to fill out the pattern that are
    missing in the input Excel and to associate edge types along the directed
    edges. Furthermore, while the Vertex is packaged in to_uml_json() the
    translator provides metadata information required by MagicDraw for block
    creation keyed by the node_type.

    Parameters
    ----------
    data : dictionary
        The JSON data saved off when the Manager accessed the JSON file.
    """

    def __init__(self, json_data=None):
        self.data = json_data

    def get_root_node(self):
        return self.data['Root Node']

    def get_cols_to_nav_map(self):
        return self.data['Columns to Navigation Map']

    def get_pattern_graph(self):
        return self.data['Pattern Graph Vertices']

    def get_pattern_graph_edges(self):
        return self.data['Pattern Graph Edges']

    def get_edge_type(self, index=None):
        return self.data['Pattern Graph Edge Labels'][index]

    def get_col_uml_names(self, column=None):
        return self.data['Columns to Navigation Map'][column][-1]

    def get_uml_metatype(self, node_key=None):
        return self.data['Vertex MetaTypes'][node_key]

    def get_uml_stereotype(self, node_key=None):
        return self.data['Vertex Stereotypes'][node_key]

    def get_uml_settings(self, node_key=None):
        uml_phrase = self.data['Vertex Settings'][node_key]

        try:
            uml_phrase.keys()
        except AttributeError:
            return node_key, uml_phrase

        key = next(iter(uml_phrase))
        return key, uml_phrase[key]
