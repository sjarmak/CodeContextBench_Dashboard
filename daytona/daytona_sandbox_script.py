from daytona import Daytona, DaytonaConfig

config = DaytonaConfig(api_key="dtn_4f0126f8f02c610c7a57fbc06f52c354d657def8852b434e5146e6b3796a0420")

# Initialize the Daytona client
daytona = Daytona(config)

# Create the Sandbox instance
sandbox = daytona.create()

# Run the code securely inside the Sandbox
response = sandbox.process.code_run('print("Hello World from code!")')
if response.exit_code != 0:
  print(f"Error: {response.exit_code} {response.result}")
else:
    print(response.result)
