import requests
from bs4 import BeautifulSoup
from typing import List, Union
from colorama import Fore, Style
from urllib.parse import urlparse
import concurrent.futures
import time
import os
from rich import print

BASE_URL = "https://brawlify.com"
STATS_CLUBS_URL = BASE_URL + "/stats/clubs/global"
TABLE_CLASS = 'table table-dark psta-color table-stats tb-stats'
LINK_CLASS = 'link opacity shadow-normal c-color-text'


class InvalidURLException(Exception):
    pass


class HTMLFetchError(Exception):
    pass


class TableNotFoundError(Exception):
    pass


class ClubEligibilityError(Exception):
    pass


def clear_console():
    os.system('cls' if os.name == 'nt' else 'clear')


def get_html(url: str) -> BeautifulSoup:
    try:
        response = requests.get(url)
        response.raise_for_status()
        return BeautifulSoup(response.content, 'html.parser')
    except requests.exceptions.RequestException as e:
        raise HTMLFetchError(f"Error fetching HTML from {url}: {e}")


def get_locations() -> List[str]:
    soup = get_html(STATS_CLUBS_URL)
    if soup is None:
        return []
    locations_div = soup.find('div', {'id': 'locations'})
    anchors = locations_div.find_all('a')
    hrefs = [BASE_URL + a['href'] for a in anchors]
    return hrefs


def is_valid_url(url: str) -> bool:
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except ValueError:
        return False


def get_club_data(hrefs: Union[str, List[str]]) -> List[dict]:
    if isinstance(hrefs, str):
        hrefs = [hrefs]

    club_data = []
    for href in hrefs:
        if not is_valid_url(href):
            print(f"Skipping invalid URL: {href}")
            continue

        try:
            soup = get_html(href)
            if soup is None:
                continue

            table = soup.find('table', {'class': TABLE_CLASS})
            if table is None:
                raise TableNotFoundError(f"No table found in {href}")

            rows = table.find_all('tr')

            for row in rows:
                data = row.find_all('td')
                club_name = data[0].find('a', {'class': LINK_CLASS})
                club_url = BASE_URL + club_name.get('href')
                club_name = club_name.text
                members = data[1].text.strip()

                club_data.append({
                    'club_name': club_name,
                    'club_url': club_url,
                    'members': members,
                })
        except HTMLFetchError as e:
            print(e)
        except TableNotFoundError as e:
            print(e)
    return club_data


def check_club_eligibility(club_url, required_trophies_limit, eligible_club_type):
    try:
        response = requests.get(club_url)

        if response.status_code == 429:
            time.sleep(10)
            return check_club_eligibility(club_url, required_trophies_limit, eligible_club_type)
        elif response.status_code != 200:
            print(f"Unexpected status code: {response.status_code}")
            return False

        soup = BeautifulSoup(response.text, 'html.parser')

        table = soup.find('table', {'class': 'table table-sm psta-color table-stats tb-stats'})
        trophies_eligible = False
        type_eligible = False
        eligible_trophies = None

        if table is None:
            return False

        for row in table.find_all('tr'):
            th = row.find('th', {'class': 'text-hp font-weight-normal'})

            if th:
                if "Required Trophies" in th.text:
                    td_text = th.find_next_sibling('td').text
                    required_trophies = int(td_text.replace(',', ''))
                    if required_trophies < required_trophies_limit:
                        trophies_eligible = True
                elif "Trophies" in th.text:
                    td_text = th.find_next_sibling('td').text
                    eligible_trophies = int(td_text.replace(',', ''))
                    if 1 < eligible_trophies:
                        trophies_eligible = True
                elif "Type" in th.text:
                    td_text = th.find_next_sibling('td').text
                    if td_text.strip().lower() == eligible_club_type:
                        type_eligible = True

            if trophies_eligible and type_eligible:
                break

        return trophies_eligible and type_eligible and eligible_trophies
    except requests.exceptions.RequestException as e:
        raise ClubEligibilityError(f"Error checking club eligibility for {club_url}: {e}")


def process_club(club, required_trophies_limit, eligible_club_type):
    club_name = club['club_name'].strip()
    members = club['members']
    club_url = club['club_url']
    if int(members.split('/')[0].strip()) < 30:
        try:
            if check_club_eligibility(club_url, required_trophies_limit, eligible_club_type):
                eligible_trophies = check_club_eligibility(club_url, required_trophies_limit, eligible_club_type)
                print(f"[green]Eligible Club: {club_name}, Members: {members}, Trophies: {eligible_trophies}, URL: {club_url}[/]")
            else:
                print(f"[red]Ineligible Club: {club_name}, Trophies: {club_url}[/]")
        except ClubEligibilityError as e:
            print(e)


def process_country(country, required_trophies_limit, eligible_club_type):
    club_data = get_club_data(country)

    with concurrent.futures.ThreadPoolExecutor() as executor:
        executor.map(lambda club: process_club(club, required_trophies_limit, eligible_club_type), club_data)


def main_menu():
    while True:
        clear_console()
        print("Main Menu:")
        print(f"[[blue]1[/]] Search for eligible clubs")
        print(f"[[blue]2[/]] GitHub")
        print(f"[[red]3[/]] Exit")
        choice = input("Enter your choice: ")
        if choice == "1":
            countries = get_locations()
            for country in countries:
                try:
                    required_trophies_limit = int(input("Enter your trophies: "))
                    print("Choose the eligible club type:")
                    print("[1] Open")
                    print("[2] Invite Only")
                    print("[3] Closed")
                    choice = input("Enter your choice (1, 2, or 3): ")
                    if choice == "1":
                        eligible_club_type = "open"
                    elif choice == "2":
                        eligible_club_type = "invite only"
                    elif choice == "3":
                        eligible_club_type = "closed"
                    else:
                        print("Invalid choice. Skipping country.")
                        continue
                    process_country(country, required_trophies_limit, eligible_club_type)
                except ValueError:
                    print("Invalid input. Please enter a valid number.")
                except KeyboardInterrupt:
                    print("Process interrupted. Exiting...")
                    break
        elif choice == "2":
            print("GitHub repository: https://github.com/pinkstoney/HDrezka-Downloader.git")
            input("Press enter to continue...")
            main_menu()
        elif choice == "3":
            print("Exiting...")
            break
        else:
            print("Invalid choice. Please enter a valid number.")


if __name__ == "__main__":
    main_menu()
