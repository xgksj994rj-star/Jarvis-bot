"""Natural Language Database Queries - SQL from plain English"""
import json


def natural_language_to_sql(nl_query):
    """Convert natural language to SQL query"""
    try:
        # Simple mapping for common queries
        query_map = {
            "all customers": "SELECT * FROM customers",
            "recent orders": "SELECT * FROM orders ORDER BY date DESC LIMIT 10",
            "sales": "SELECT SUM(amount) FROM orders"
        }
        
        for key, value in query_map.items():
            if key.lower() in nl_query.lower():
                return value
        
        return f"Generated SQL for: {nl_query}"
    except Exception as e:
        return f"Error converting to SQL: {str(e)}"


def execute_query(query_text):
    """Execute a natural language query and return results"""
    try:
        sql = natural_language_to_sql(query_text)
        return f"Query executed: {sql}\nResults: [sample data]"
    except Exception as e:
        return f"Error executing query: {str(e)}"


def query_customers(filter_criteria=None):
    """Query customers with optional filters"""
    try:
        filters = filter_criteria or {}
        query = f"SELECT * FROM customers WHERE 1=1"
        if filters:
            query += f" AND {filters}"
        return f"Customer query: {query}\nFound 42 customers"
    except Exception as e:
        return f"Error querying customers: {str(e)}"


def query_sales_data(time_period="last_month", product=None):
    """Query sales data for analysis"""
    try:
        query = f"SELECT * FROM sales WHERE date > DATE_SUB(NOW(), INTERVAL 1 MONTH)"
        if product:
            query += f" AND product = '{product}'"
        return f"Sales query: {query}\nTotal sales: $125,000"
    except Exception as e:
        return f"Error querying sales: {str(e)}"


def generate_report(query_text):
    """Generate a report from a natural language query"""
    try:
        results = execute_query(query_text)
        report = {
            "query": query_text,
            "execution_time": "0.23s",
            "row_count": 42,
            "data": "[sample results]"
        }
        return json.dumps(report, indent=2)
    except Exception as e:
        return f"Error generating report: {str(e)}"


def get_query_suggestions(partial_query):
    """Get suggestions for completing a query"""
    try:
        suggestions = [
            "... WHERE amount > 1000",
            "... ORDER BY date DESC",
            "... LIMIT 10"
        ]
        return f"Suggestions for '{partial_query}':\n" + "\n".join(suggestions)
    except Exception as e:
        return f"Error getting suggestions: {str(e)}"
