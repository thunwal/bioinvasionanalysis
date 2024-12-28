from pathlib import Path
import ipywidgets as widgets
from IPython.display import display

# Define a dictionary to store parameter values
param_values = {}

# Button click handler for the params widget
def save_params(workdir_path_w, presence_name_w, year_field_w, location_field_w, start_year_w, end_year_w, cost_name_w, run_w, output):
    param_values['workdir_path'] = workdir_path_w.value
    param_values['presence_name'] = presence_name_w.value
    param_values['year_field'] = year_field_w.value
    param_values['location_field'] = location_field_w.value
    param_values['start_year'] = start_year_w.value
    param_values['end_year'] = end_year_w.value
    param_values['cost_name'] = cost_name_w.value
    param_values['run'] = run_w.value

    with output:
        output.clear_output()  # Clear previous output
        print("Parameters are saved.")

# Button click handler for the threshold widget
def save_threshold(threshold_w, output):
    param_values['threshold'] = threshold_w.value

    with output:
        output.clear_output()  # Clear previous output
        print("Threshold is saved.")

def params_widget():
    # Set default data directory
    default_workdir_path = Path().resolve().parent / "data"

    # Define defaults for widgets
    default_layout = widgets.Layout(width='auto')
    style = {'description_width': 'initial'}

    # Define widgets for each parameter
    workdir_path_w = widgets.Text(
        description="Data directory:",
        layout=default_layout, style=style,
        value=str(default_workdir_path)
    )
    presence_name_w = widgets.Text(
        description="Observation data file name:",
        layout=default_layout, style=style,
        value="imexicana_20241227.gpkg"
    )
    year_field_w = widgets.Text(
        description="Field containing observation year:",
        layout=default_layout, style=style,
        value="year"
    )
    location_field_w = widgets.Text(
        description="Field containing observation location:",
        layout=default_layout, style=style,
        value="countryCode"
    )
    start_year_w = widgets.IntText(
        description="Start analysis with year:",
        layout=default_layout, style=style,
        value=1993
    )
    end_year_w = widgets.IntText(
        description="End analysis with year:",
        layout=default_layout, style=style,
        value=2024
    )
    cost_name_w = widgets.Text(
        description="Cost surface file name:",
        layout=default_layout, style=style,
        value="cost_surface_gtopo30_esri102031_5km_exp_rescaled.tif"
    )
    run_w = widgets.Text(
        description="Prefix for output files:",
        layout=default_layout, style=style,
        value="demo"
    )

    # Button to submit the form
    submit_button = widgets.Button(description="Submit", button_style='success')

    # Output widget to display the results
    output = widgets.Output()

    # Attach the event handler to the button
    submit_button.on_click(lambda b: save_params(workdir_path_w, presence_name_w, year_field_w, location_field_w, start_year_w, end_year_w, cost_name_w, run_w, output))

    # Arrange the widgets in a vertical form
    form = widgets.VBox(
        [workdir_path_w, presence_name_w, location_field_w, year_field_w, start_year_w, end_year_w,
         cost_name_w, run_w, submit_button, output])

    # Display the form
    display(form)

def threshold_widget(outlier_quantile):
    # Define defaults for widgets
    default_layout = widgets.Layout(width='auto')
    style = {'description_width': 'initial'}

    # Define widget
    threshold_w = widgets.FloatText(
        description="Accumulated cost threshold (quantile):",
        layout=default_layout, style=style,
        value=outlier_quantile
    )

    # Button to submit the form
    submit_button = widgets.Button(description="Submit", button_style='success')

    # Output widget to display the results
    output = widgets.Output()

    # Attach the event handler to the button
    submit_button.on_click(lambda b: save_threshold(threshold_w, output))

    # Display the form
    display(widgets.VBox([threshold_w, submit_button, output]))

# Function to get saved parameters
def get_params():
    return param_values
