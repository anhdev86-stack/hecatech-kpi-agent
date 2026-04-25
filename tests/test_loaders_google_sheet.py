from kpi_agent.loaders import to_google_sheet_export_url


def test_google_sheet_url_to_export_url():
    url = "https://docs.google.com/spreadsheets/d/1VtwiBZb-wq3ZX4ss-lYvcJqfsgZIZhifotu7dszw_m4/edit?gid=383907200#gid=383907200"
    out = to_google_sheet_export_url(url)
    assert out == "https://docs.google.com/spreadsheets/d/1VtwiBZb-wq3ZX4ss-lYvcJqfsgZIZhifotu7dszw_m4/export?format=xlsx"
