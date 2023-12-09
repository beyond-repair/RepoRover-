import datetime
import concurrent.futures
import os 
from bs4 import BeautifulSoup
import csv
import logging
import requests
from nltk.stem.porter import PorterStemmer
from nltk.stem import WordNetLemmatizer
from nltk.tokenize import word_tokenize
from nltk.corpus import stopwords


# Define base URL, CSV file path, and maximum concurrent connections
base_url = "https://github.com"
csv_file_path = "readmeMD.csv"
max_workers = 4

# Define header row for CSV file
headers = ["Processed At", "Repository Name", "Homepage URL", "Processed Readme.MD Content"]

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


def get_repo_urls(page_url):
    """
    Fetches the provided URL and extracts links to GitHub repositories.

    Args:
        page_url: URL of the webpage containing repository links.

    Returns:
        list: List of extracted repository URLs.
    """
    try:
        response = requests.get(page_url)

        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
            repo_links = soup.select("h1[class='h3 lh-condensed'] a[href]")
            return [f"{base_url}{link['href']}" for link in repo_links]
        else:
            logging.warning(f"Failed to fetch {page_url}. Status code: {response.status_code}")
    except Exception as e:
        logging.error(f"Error processing page {page_url}: {e}")

    return []


def get_readme_content(repo_url, retries=3):
    """
    Attempts to retrieve the content of the README.md file for a given repository URL.

    Args:
        repo_url: URL of the GitHub repository.
        retries: Number of retries to attempt if the request fails.

    Returns:
        str: Content of the README.md file or None if retrieval fails.
    """
    try:
        response = requests.get(repo_url)

        if response.status_code == 200:
            soup = BeautifulSoup(response.content, "html.parser")

            # Find readme link
            readme_link = soup.find("a", {"id": "readme-permalink"})

            if readme_link:
                readme_url = f"{base_url}{readme_link['href']}"

                # Retrieve and return README.md content
                readme_response = requests.get(readme_url)
                if readme_response.status_code == 200:
                    return readme_response.text
                else:
                    logging.warning(f"Error retrieving readme.MD from {repo_url}")
            else:
                logging.info(f"No readme.MD found in {repo_url}")

        elif retries > 0:
            time.sleep(1)
            return get_readme_content(repo_url, retries=retries - 1)
        else:
            logging.warning(f"Error accessing repository {repo_url}")

    except requests.RequestException as e:
        logging.error(f"Request error processing repository {repo_url}: {e}")

    except Exception as e:
        logging.error(f"Error processing repository {repo_url}: {e}")

    return None


def preprocess_content(content, custom_processing=False):
    """
    Preprocesses the provided content by performing:

    1. Lowercase conversion
    2. HTML tag removal
    3. Tokenization
    4. Removal of stop words
    5. Stemming or lemmatization

    Args:
        content: String containing the content to be preprocessed.
        custom_processing: Boolean flag indicating whether to use lemmatization instead of stemming.

    Returns:
        str: Preprocessed content.
    """
    preprocessed_content = content.lower()

    # Remove HTML tags
    soup = BeautifulSoup(preprocessed_content, "html.parser")
    preprocessed_content = soup.get_text()

    # Tokenization
    tokens = word_tokenize(preprocessed_content)

    # Remove stop words
    stop_words = stopwords.words("english")
    filtered_tokens = [token for token in tokens if token not in stop_words]


    # Stemming or lemmatization
    if custom_processing:
        lemmatizer = WordNetLemmatizer()
        processed_tokens = [lemmatizer.lemmatize(token) for token in filtered_tokens]
    else:
        stemmer = PorterStemmer()
        processed_tokens = [stemmer.stem(token) for token in filtered_tokens]

    # Preprocessed content ready for further processing
    preprocessed_content = " ".join(processed_tokens)

    return preprocessed_content


def write_to_csv(data):
    """
    Writes the provided data dictionary to the designated CSV file.

    Args:
        data: Dictionary containing processed repository information.
    """
    with open(csv_file_path, "a", newline="") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=headers)
        writer.writerow(data)


def process_repository(repo_url, existing_data):
    """
    Processes a single repository by:

    1. Extracting its README.md content.
    2. Preprocessing the content.
    3. Checking for duplicate entries.
    4. Writing the processed data to the CSV file if not a duplicate.

    Args:
        repo_url: URL of the GitHub repository.
        existing_data: List of dictionaries containing previously processed repository information.
    """
    # Extract readme.MD content
    readme_content = get_readme_content(repo_url)

    # Check if data is valid
    if readme_content:
        # Parse HTML content of the readme
        soup = BeautifulSoup(readme_content, "html.parser")

        # Extract repository name
        repo_name = soup.find("h1", {"class": "public"}).text.strip()

        # Check for duplicate entries
        if any(repo_name == row["Repository Name"] for row in existing_data):
            logging.info(f"Skipping duplicate repository: {repo_name}")
            return

        # Pre-process data with lemmatization
        preprocessed_content = preprocess_content(readme_content, custom_processing=True)

        # Prepare data for writing
        data = {
            "Processed At": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "Repository Name": repo_name,
            "Homepage URL": repo_url,
            "Processed Readme.MD Content": preprocessed_content,
        }

        # Write data to CSV file
        write_to_csv(data)
        logging.info(f"Processed repository: {repo_name}")


def main():
    """
    Main function that orchestrates the scraping and processing of GitHub Readme.MD files.

    1. Checks if the CSV file exists and creates it if not.
    2. Reads existing data from the CSV file.
    3. Defines a list of repository URLs to process.
    4. Utilizes a ThreadPoolExecutor to process each repository concurrently.
    5. Logs information about the completed process.
    """
    # Check if CSV file exists, create it if not
    if not os.path.isfile(csv_file_path):
        with open(csv_file_path, "w", newline="") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=headers)
            writer.writeheader()

    # Read existing data from CSV file
    existing_data = []
    with open(csv_file_path, "r") as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            existing_data.append(row)

    # Define explore page URL
    explore_page_url = "https://github.com/explore"

    # Gather repository URLs from the explore page
    repo_urls = get_repo_urls(explore_page_url)

    # Check if any URLs were found
    if not repo_urls:
        logging.info("No repository URLs found on the explore page.")
        return

    # Process each repository concurrently
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        executor.map(process_repository, repo_urls, existing_data)

    logging.info(f"Scouring completed. Processed data saved to {csv_file_path}")


if __name__ == "__main__":
    main()