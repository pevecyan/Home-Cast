# Use an official Python runtime as a parent image
FROM python:3.12-slim

# Set environment variables
ENV FLASK_APP=app.py \
    FLASK_ENV=production

# Set working directory in the container
WORKDIR /usr/src/app

# Copy application files to the container
COPY . .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Expose port 5000 for Flask app to listen on
EXPOSE 5000

# Run the entrypoint script to start the server
CMD ["python", "app.py"]