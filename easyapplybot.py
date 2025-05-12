import time, random, os, csv
import logging
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import pandas as pd
import re
import yaml
from datetime import datetime, timedelta
import undetected_chromedriver as uc
from dotenv import load_dotenv

load_dotenv()

USERNAME = os.getenv('USERNAME')
PASSWORD = os.getenv('PASSWORD')
PHONE_NUMBER = os.getenv('PHONE_NUMBER')
SALARY = os.getenv('SALARY')
RATE = os.getenv('RATE')

log = logging.getLogger(__name__)


def setupLogger():
    dt = datetime.strftime(datetime.now(), "%m_%d_%y %H_%M_%S ")

    if not os.path.isdir('./logs'):
        os.mkdir('./logs')

    # TODO need to check if there is a log dir available or not
    logging.basicConfig(filename=('./logs/' + str(dt) + 'applyJobs.log'), filemode='w',
                        format='%(asctime)s::%(name)s::%(levelname)s::%(message)s', datefmt='./logs/%d-%b-%y %H:%M:%S')
    log.setLevel(logging.DEBUG)
    c_handler = logging.StreamHandler()
    c_handler.setLevel(logging.DEBUG)
    c_format = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', '%H:%M:%S')
    c_handler.setFormatter(c_format)
    log.addHandler(c_handler)


class EasyApplyBot:
    setupLogger()
    # MAX_SEARCH_TIME is 10 hours by default, feel free to modify it
    MAX_SEARCH_TIME = 10 * 60 * 60

    def __init__(
        self,
        username: str,
        password: str,
        phone_number: str = '',
        salary: str = '',
        rate: str = '',
        uploads: dict = {},
        filename: str = 'output.csv',
        blacklist: list = [],
        blackListTitles: list = [],
        experience_level: list = []
    ) -> None:
        assert username, "Username is required."
        assert password, "Password is required."
        self.username: str = username
        self.password: str = password
        self.phone_number: str = phone_number
        self.salary: str = salary
        self.rate: str = rate
        self.uploads: dict = uploads
        self.filename: str = filename
        self.blacklist: list = blacklist
        self.blackListTitles: list = blackListTitles
        self.experience_level: list = experience_level

        log.info("Welcome to Easy Apply Bot")
        dirpath = os.getcwd()
        log.info("current directory is : " + dirpath)
        log.info("Please wait while we prepare the bot for you")

        # Locator dictionary for all selectors
        self.locator = {
            "next": (By.CSS_SELECTOR, "button[aria-label='Continue to next step']"),
            "review": (By.CSS_SELECTOR, "button[aria-label='Review your application']"),
            "submit": (By.CSS_SELECTOR, "button[aria-label='Submit application']"),
            "error": (By.CSS_SELECTOR, "p[data-test-form-element-error-message='true']"),
            "upload": (By.CSS_SELECTOR, "input[name='file']"),
            "follow": (By.CSS_SELECTOR, "label[for='follow-company-checkbox']"),
            "search": (By.CLASS_NAME, "job-card-list"),
            "links": (By.XPATH, '//div[@data-job-id]'),
            "fields": (By.CLASS_NAME, "jobs-easy-apply-form-section__grouping"),
            "radio_select": (By.CSS_SELECTOR, "input[type='radio']"),
            "multi_select": (By.XPATH, "//*[contains(@id, 'text-entity-list-form-component')]") ,
            "text_select": (By.CLASS_NAME, "artdeco-text-input--input"),
            "easy_apply_button": (By.CLASS_NAME, 'jobs-apply-button'),
            "username": (By.ID, "username"),
            "password": (By.ID, "password"),
            "login_button": (By.CSS_SELECTOR, ".btn__primary--large"),
        }

        # Q&A persistent storage
        from pathlib import Path
        self.qa_file = Path("qa.csv")
        self.answers = {}
        if self.qa_file.is_file():
            df = pd.read_csv(self.qa_file)
            for index, row in df.iterrows():
                self.answers[row['Question']] = row['Answer']
        else:
            df = pd.DataFrame(columns=["Question", "Answer"])
            df.to_csv(self.qa_file, index=False, encoding='utf-8')

        past_ids = self.get_appliedIDs(filename)
        self.appliedJobIDs: list = past_ids if past_ids is not None else []
        self.options = self.browser_options()
        self.browser = uc.Chrome(options=self.options)
        self.browser.fullscreen_window()
        self.wait = WebDriverWait(self.browser, 30)
        self.start_linkedin(self.username, self.password)
        time.sleep(5)
        log.info("Bot initialization complete.")
        

    def get_appliedIDs(self, filename: str) -> list | None:
        print(f"[DEBUG] Loading applied IDs from {filename}")
        try:
            df = pd.read_csv(filename,
                             header=None,
                             names=['timestamp', 'jobID', 'job', 'company', 'attempted', 'result'],
                             lineterminator='\n',
                             encoding='utf-8')

            df['timestamp'] = pd.to_datetime(df['timestamp'], format="%Y-%m-%d %H:%M:%S")
            df = df[df['timestamp'] > (datetime.now() - timedelta(days=2))]
            jobIDs = list(df.jobID)
            log.info(f"{len(jobIDs)} jobIDs found")
            print(f"[DEBUG] {len(jobIDs)} jobIDs found in CSV")
            return jobIDs
        except Exception as e:
            log.info(str(e) + "   jobIDs could not be loaded from CSV {}".format(filename))
            print(f"[DEBUG] Exception in get_appliedIDs: {e}")
            return None

    def browser_options(self) -> Options:
        print("[DEBUG] Setting browser options")
        options = Options()
        options.add_argument("--start-maximized")
        options.add_argument("--ignore-certificate-errors")
        options.add_argument('--no-sandbox')
        options.add_argument("--disable-extensions")

        # Disable webdriver flags or you will be easily detectable
        options.add_argument("--disable-blink-features")
        options.add_argument("--disable-blink-features=AutomationControlled")
        print("[DEBUG] Browser options set")
        return options

    def start_linkedin(self, username: str, password: str) -> None:
        print("[DEBUG] Logging into LinkedIn...")
        log.info("Logging in.....Please wait :)  ")
        self.browser.get("https://www.linkedin.com/login?trk=guest_homepage-basic_nav-header-signin")
        try:
            user_field = self.get_elements('username')[0] if self.is_present((By.ID, "username")) else None
            pw_field = self.get_elements('password')[0] if self.is_present((By.ID, "password")) else None
            login_button = self.get_elements('login_button')[0] if self.is_present((By.CSS_SELECTOR, ".btn__primary--large")) else None
            user_field.send_keys(username)
            user_field.send_keys(Keys.TAB)
            time.sleep(2)
            pw_field.send_keys(password)
            time.sleep(2)
            login_button.click()
            time.sleep(3)
            print("[DEBUG] Login submitted")
        except TimeoutException:
            log.info("TimeoutException! Username/password field or login button not found")
            print("[DEBUG] TimeoutException during login")

    def fill_data(self) -> None:
        print("[DEBUG] Moving browser window off-screen")
        self.browser.set_window_position(2000, 2000)

    def start_apply(self, positions: list, locations: list) -> None:
        print(f"[DEBUG] Starting job application process for positions: {positions}, locations: {locations}")
        start = time.time()
        self.fill_data()

        combos = []
        while len(combos) < len(positions) * len(locations):
            position = positions[random.randint(0, len(positions) - 1)]
            location = locations[random.randint(0, len(locations) - 1)]
            combo = (position, location)
            if combo not in combos:
                combos.append(combo)
                log.info(f"Applying to {position}: {location}")
                print(f"[DEBUG] Applying to {position} in {location}")
                location = "&location=" + location
                self.applications_loop(position, location)
            if len(combos) > 500:
                print("[DEBUG] Combo limit reached, breaking loop")
                break

    def applications_loop(self, position: str, location: str) -> None:
        print(f"[DEBUG] Entering applications_loop for {position} in {location}")
        count_application = 0
        count_job = 0
        jobs_per_page = 0
        start_time = time.time()

        log.info("Looking for jobs.. Please wait..")

        self.browser.set_window_position(0, 0)
        self.browser.maximize_window()
        self.browser, _ = self.next_jobs_page(position, location, jobs_per_page)
        log.info("Looking for jobs.. Please wait..")

        while time.time() - start_time < self.MAX_SEARCH_TIME:
            try:
                log.info(f"{(self.MAX_SEARCH_TIME - (time.time() - start_time)) // 60} minutes left in this search")
                print(f"[DEBUG] {int((self.MAX_SEARCH_TIME - (time.time() - start_time)) // 60)} minutes left in search loop")

                # sleep to make sure everything loads, add random to make us look human.
                randoTime = random.uniform(3.5, 4.9)
                log.debug(f"Sleeping for {round(randoTime, 1)}")
                print(f"[DEBUG] Sleeping for {round(randoTime, 1)} seconds")
                time.sleep(randoTime)
                self.load_page(sleep=1)

                # DEBUG: Print all class names and IDs on the page before searching for jobs-search-results
                page_source = self.browser.page_source
                soup = BeautifulSoup(page_source, 'lxml')
                all_classes = set()
                all_ids = set()
                for tag in soup.find_all(True):
                    if tag.has_attr('class'):
                        for c in tag['class']:
                            all_classes.add(c)
                    if tag.has_attr('id'):
                        all_ids.add(tag['id'])
                # print(f"[DEBUG] Classes found on page: {sorted(list(all_classes))}")
                print(f"[DEBUG] IDs found on page: {sorted(list(all_ids))}")
                # Optionally, print a snippet of the HTML
                # print(f"[DEBUG] HTML snippet: {page_source[:1000]}")

                # Only look for job-card-list if on the search results page
                if "linkedin.com/jobs/search" in self.browser.current_url:
                    scrollresults = self.get_elements('search')[0] if self.is_present(self.locator['search']) else None
                else:
                    scrollresults = None

                # Selenium only detects visible elements; if we scroll to the bottom too fast, only 8-9 results will be loaded into IDs list
                if scrollresults:
                    for i in range(300, 3000, 100):
                        self.browser.execute_script("arguments[0].scrollTo(0, {})".format(i), scrollresults)

                time.sleep(1)

                # get job links
                links = self.get_elements('links')
                print(f"[DEBUG] Found {len(links)} job links on page")
                for idx, link in enumerate(links):
                    try:
                        print(f"[DEBUG] Link {idx} outer HTML: {link.get_attribute('outerHTML')[:500]}")
                        # print(f"[DEBUG] Link {idx} attributes: {[attr for attr in dir(link) if not attr.startswith('_')]}")
                    except Exception as e:
                        print(f"[DEBUG] Exception printing link {idx}: {e}")

                if len(links) == 0:
                    print("[DEBUG] No job links found, breaking loop")
                    break

                # get job ID of each job link
                IDs = []
                for link in links:
                    job_id = link.get_attribute("data-job-id")
                    if job_id:
                        IDs.append(int(job_id))
                IDs = set(IDs)
                print(f"[DEBUG] Extracted {len(IDs)} unique job IDs")

                # remove already applied jobs
                before = len(IDs)
                jobIDs = [x for x in IDs if x not in self.appliedJobIDs]
                after = len(jobIDs)
                print(f"[DEBUG] Filtered jobIDs: {after} remaining (from {before})")

                # it assumed that 25 jobs are listed in the results window
                if len(jobIDs) == 0 and len(IDs) > 23:
                    jobs_per_page = jobs_per_page + 25
                    count_job = 0
                    self.avoid_lock()
                    self.browser, jobs_per_page = self.next_jobs_page(position,
                                                                    location,
                                                                    jobs_per_page)
                # loop over IDs to apply
                for i, jobID in enumerate(jobIDs):
                    count_job += 1
                    print(f"[DEBUG] Processing jobID: {jobID}")
                    self.get_job_page(jobID)

                    # get easy apply button
                    button_clicked = self.get_easy_apply_button()
                    # word filter to skip positions not wanted

                    if button_clicked:
                        if any(word in self.browser.title for word in self.blackListTitles):
                            log.info('skipping this application, a blacklisted keyword was found in the job position')
                            print(f"[DEBUG] Skipping jobID {jobID} due to blacklisted title")
                            string_easy = "* Contains blacklisted keyword"
                            result = False
                        else:
                            string_easy = "* has Easy Apply Button"
                            log.info("Clicking the EASY apply button")
                            print(f"[DEBUG] Clicking Easy Apply for jobID {jobID}")
                            time.sleep(3)
                            result = self.send_resume()
                            count_application += 1
                    else:
                        log.info("The button does not exist.")
                        print(f"[DEBUG] No Easy Apply button for jobID {jobID}")
                        string_easy = "* Doesn't have Easy Apply Button"
                        result = False

                    position_number = str(count_job + jobs_per_page)
                    log.info(f"\nPosition {position_number}:\n {self.browser.title} \n {string_easy} \n")

                    self.write_to_file(button_clicked, jobID, self.browser.title, result)
                    print(f"[DEBUG] Wrote result for jobID {jobID} to file")

                    # sleep every 20 applications
                    if count_application != 0 and count_application % 20 == 0:
                        sleepTime = random.randint(500, 900)
                        log.info(f"********count_application: {count_application}************\n\n"
                                 f"Time for a nap - see you in: {int(sleepTime / 60)} min\n"
                                 "****************************************\n\n")
                        print(f"[DEBUG] Sleeping for {sleepTime} seconds after 20 applications")
                        time.sleep(sleepTime)

                    # go to new page if all jobs are done
                    
                    if count_job == len(jobIDs):
                        jobs_per_page = jobs_per_page + 25
                        count_job = 0
                        log.info("""****************************************\n\n
                        Going to next jobs page, YEAAAHHH!!
                        ****************************************\n\n""")
                        print("[DEBUG] Going to next jobs page")
                        self.avoid_lock()
                        self.browser, jobs_per_page = self.next_jobs_page(position,
                                                                        location,
                                                                        jobs_per_page)
            except Exception as e:
                print(f"[DEBUG] Exception in applications_loop: {e}")
                log.info(e)

    def write_to_file(self, button: bool, jobID: int, browserTitle: str, result: bool) -> None:
        print(f"[DEBUG] Writing to file for jobID {jobID}")
        def re_extract(text, pattern):
            target = re.search(pattern, text)
            if target:
                target = target.group(1)
            return target

        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        attempted = False if button == False else True
        job = re_extract(browserTitle.split(' | ')[0], r"\(?\d?\)?\s?(\w.*)")
        company = re_extract(browserTitle.split(' | ')[1], r"(\w.*)")

        toWrite = [timestamp, jobID, job, company, attempted, result]
        with open(self.filename, 'a') as f:
            writer = csv.writer(f)
            writer.writerow(toWrite)
        print(f"[DEBUG] Finished writing to file for jobID {jobID}")

    def get_job_page(self, jobID: int) -> BeautifulSoup:
        print(f"[DEBUG] Navigating to job page for jobID {jobID}")
        job = 'https://www.linkedin.com/jobs/view/' + str(jobID)
        self.browser.get(job)
        self.job_page = self.load_page(sleep=0.5)
        # Scroll to the top to ensure Easy Apply button is visible
        self.browser.execute_script("window.scrollTo(0, 0);")
        time.sleep(1)
        return self.job_page

    def get_easy_apply_button(self) -> bool:
        print("[DEBUG] Looking for Easy Apply button")
        try:
            buttons = self.browser.find_elements(By.CLASS_NAME, 'jobs-apply-button')
            print(f"[DEBUG] Found {len(buttons)} buttons with class 'jobs-apply-button'")
            for idx, btn in enumerate(buttons):
                try:
                    btn_text = btn.text.strip()
                    btn_displayed = btn.is_displayed()
                    btn_enabled = btn.is_enabled()
                    btn_aria = btn.get_attribute('aria-label')
                    print(f"[DEBUG] Button {idx}: text={btn_text}, displayed={btn_displayed}, enabled={btn_enabled}, aria-label={btn_aria}")
                    if btn_displayed and btn_enabled and ('Easy Apply' in btn_text or 'Easy Apply' in (btn_aria or '')):
                        # Scroll to center
                        self.browser.execute_script("arguments[0].scrollIntoView({block: 'center'});", btn)
                        time.sleep(0.5)
                        # Close overlays
                        self.browser.find_element(By.TAG_NAME, 'body').send_keys(Keys.ESCAPE)
                        time.sleep(0.5)
                        try:
                            btn.click()
                            print("[DEBUG] Easy Apply button clicked (normal click).")
                        except Exception as click_exc:
                            print(f"[DEBUG] Normal click failed: {click_exc}, trying JS click.")
                            self.browser.execute_script("arguments[0].click();", btn)
                            print("[DEBUG] Easy Apply button clicked (JS click).")
                        return True
                except Exception as be:
                    print(f"[DEBUG] Exception checking button {idx}: {be}")
            print("[DEBUG] No visible and enabled Easy Apply button found.")
            return False
        except Exception as e:
            print(f"[DEBUG] Exception in get_easy_apply_button: {e}")
            return False

    def ans_question(self, question: str) -> str:
        answer = None
        q = question.lower()
        if "how many" in q:
            answer = "1"
        elif "experience" in q:
            answer = "1"
        elif "sponsor" in q:
            answer = "No"
        elif 'do you ' in q:
            answer = "Yes"
        elif "have you " in q:
            answer = "Yes"
        elif "us citizen" in q:
            answer = "Yes"
        elif "are you " in q:
            answer = "Yes"
        elif "salary" in q:
            answer = self.salary
        elif "can you" in q:
            answer = "Yes"
        elif "gender" in q:
            answer = "Male"
        elif "race" in q:
            answer = "Wish not to answer"
        elif "lgbtq" in q:
            answer = "Wish not to answer"
        elif "ethnicity" in q:
            answer = "Wish not to answer"
        elif "nationality" in q:
            answer = "Wish not to answer"
        elif "government" in q:
            answer = "I do not wish to self-identify"
        elif "are you legally" in q:
            answer = "Yes"
        elif "phone" in q and self.phone_number:
            answer = self.phone_number
        else:
            log.info(f"Not able to answer question automatically. Please provide answer for: {question}")
            answer = "user provided"
            import time
            time.sleep(15)
        log.info(f"Answering question: {question} with answer: {answer}")
        # Append question and answer to the CSV if new
        if question not in self.answers:
            self.answers[question] = answer
            new_data = pd.DataFrame({"Question": [question], "Answer": [answer]})
            new_data.to_csv(self.qa_file, mode='a', header=False, index=False, encoding='utf-8')
            log.info(f"Appended to QA file: '{question}' with answer: '{answer}'.")
        return answer

    def process_questions(self) -> None:
        fields = self.get_elements('fields')
        for field in fields:
            question = field.text
            answer = self.ans_question(question)
            # Try to fill radio, multi, or text fields
            try:
                # radio button
                if self.is_present(self.locator["radio_select"]):
                    try:
                        input_elem = field.find_element(By.CSS_SELECTOR, f"input[type='radio'][value='{answer}']")
                        self.browser.execute_script("arguments[0].click();", input_elem)
                        continue
                    except Exception as e:
                        log.error(f"Radio select error: {e}")
                        continue
                # multi select
                elif self.is_present(self.locator["multi_select"]):
                    try:
                        input_elem = field.find_element(*self.locator["multi_select"])
                        input_elem.send_keys(answer)
                        continue
                    except Exception as e:
                        log.error(f"Multi select error: {e}")
                        continue
                # text box
                elif self.is_present(self.locator["text_select"]):
                    try:
                        input_elem = field.find_element(*self.locator["text_select"])
                        input_elem.send_keys(answer)
                        continue
                    except Exception as e:
                        log.error(f"Text select error: {e}")
                        continue
            except Exception as e:
                log.error(f"process_questions error: {e}")
                continue
        log.info("Finished processing questions.")

    def send_resume(self) -> bool:
        print("[DEBUG] Attempting to send resume...")
        def is_present(button_locator):
            return len(self.browser.find_elements(button_locator[0],
                                                  button_locator[1])) > 0

        try:
            time.sleep(random.uniform(1.5, 2.5))
            next_locater = self.locator["next"]
            review_locater = self.locator["review"]
            submit_locater = self.locator["submit"]
            error_locator = self.locator["error"]
            upload_locator = self.locator["upload"]
            follow_locator = self.locator["follow"]

            # Additional locators for resume/cover letter
            resume_upload_locator = (By.XPATH, "//*[contains(@id, 'jobs-document-upload-file-input-upload-resume')]")
            cover_letter_upload_locator = (By.XPATH, "//*[contains(@id, 'jobs-document-upload-file-input-upload-cover-letter')]")

            submitted = False
            while True:
                print("[DEBUG] In send_resume loop")
                # Upload Resume if possible
                if "Resume" in self.uploads and is_present(resume_upload_locator):
                    try:
                        resume_input = self.browser.find_element(*resume_upload_locator)
                        print(f"[DEBUG] Uploading Resume: {self.uploads['Resume']}")
                        resume_input.send_keys(self.uploads["Resume"])
                        log.info("Resume uploaded successfully.")
                    except Exception as e:
                        log.error(f"Resume upload failed: {e}")
                # Upload Cover Letter if possible
                if "Cover Letter" in self.uploads and is_present(cover_letter_upload_locator):
                    try:
                        cover_input = self.browser.find_element(*cover_letter_upload_locator)
                        print(f"[DEBUG] Uploading Cover Letter: {self.uploads['Cover Letter']}")
                        cover_input.send_keys(self.uploads["Cover Letter"])
                        log.info("Cover letter uploaded successfully.")
                    except Exception as e:
                        log.error(f"Cover letter upload failed: {e}")
                # Fallback: generic upload field
                if is_present(upload_locator):
                    print("[DEBUG] Generic upload field present, attempting upload")
                    input_buttons = self.browser.find_elements(upload_locator[0], upload_locator[1])
                    for input_button in input_buttons:
                        for key in self.uploads.keys():
                            try:
                                print(f"[DEBUG] Uploading {key} from {self.uploads[key]}")
                                input_button.send_keys(self.uploads[key])
                                log.info(f"Uploaded {key} via generic upload field.")
                            except Exception as e:
                                log.error(f"Failed to upload {key} via generic upload field: {e}")
                    time.sleep(random.uniform(2.5, 4.5))

                # Click Next or submit button if possible
                button = None
                buttons = [next_locater, review_locater, follow_locator, submit_locater]
                for i, button_locator in enumerate(buttons):
                    if is_present(button_locator):
                        button = self.wait.until(EC.element_to_be_clickable(button_locator))
                        print(f"[DEBUG] Found clickable button at step {i}")

                    if is_present(error_locator):
                        for element in self.browser.find_elements(error_locator[0], error_locator[1]):
                            text = element.text
                            if "Please enter a valid answer" in text:
                                print("[DEBUG] Found error message, cannot proceed")
                                button = None
                                break
                            else:
                                # If there are questions, process them
                                self.process_questions()
                    if button:
                        button.click()
                        print(f"[DEBUG] Clicked button at step {i}")
                        time.sleep(random.uniform(1.5, 2.5))
                        if i in (3,):
                            submitted = True
                        if i != 2:
                            break
                if button is None:
                    log.info("Could not complete submission")
                    print("[DEBUG] Could not complete submission in send_resume")
                    break
                elif submitted:
                    log.info("Application Submitted")
                    print("[DEBUG] Application submitted!")
                    break

            time.sleep(random.uniform(1.5, 2.5))

        except Exception as e:
            log.info(e)
            log.info("cannot apply to this job")
            print(f"[DEBUG] Exception in send_resume: {e}")
            raise (e)

        return submitted

    def load_page(self, sleep: float = 1) -> BeautifulSoup:
        print(f"[DEBUG] Loading page with sleep={sleep}")
        scroll_page = 0
        while scroll_page < 4000:
            self.browser.execute_script("window.scrollTo(0," + str(scroll_page) + " );")
            scroll_page += 200
            time.sleep(sleep)

        if sleep != 1:
            self.browser.execute_script("window.scrollTo(0,0);")
            time.sleep(sleep * 3)

        page = BeautifulSoup(self.browser.page_source, "lxml")
        print("[DEBUG] Page loaded and parsed with BeautifulSoup")
        return page

    def avoid_lock(self) -> None:
        print("[DEBUG] Simulating activity to avoid lock")
        # Scroll up and down to simulate activity in the browser
        try:
            self.browser.execute_script("window.scrollBy(0, 100);")
            time.sleep(0.5)
            self.browser.execute_script("window.scrollBy(0, -100);")
            time.sleep(0.5)
        except Exception as e:
            log.info(f"avoid_lock simulation failed: {e}")

    def next_jobs_page(self, position: str, location: str, jobs_per_page: int) -> tuple:
        print(f"[DEBUG] Navigating to next jobs page: position={position}, location={location}, jobs_per_page={jobs_per_page}")
        # Add experience level filtering to the URL if set
        experience_level_str = ",".join(map(str, self.experience_level)) if self.experience_level else ""
        experience_level_param = f"&f_E={experience_level_str}" if experience_level_str else ""
        self.browser.get(
            "https://www.linkedin.com/jobs/search/?f_LF=f_AL&keywords=" +
            position + location + "&start=" + str(jobs_per_page) + experience_level_param)
        self.avoid_lock()
        log.info("Lock avoided.")
        self.load_page()
        print("[DEBUG] Next jobs page loaded")
        return (self.browser, jobs_per_page)

    def finish_apply(self) -> None:
        print("[DEBUG] Closing browser")
        self.browser.close()

    def is_present(self, locator: tuple) -> bool:
        return len(self.browser.find_elements(locator[0], locator[1])) > 0

    def get_elements(self, locator_name: str) -> list:
        locator = self.locator[locator_name]
        return self.browser.find_elements(locator[0], locator[1])


if __name__ == '__main__':
    print("[DEBUG] Starting main execution block")
    with open("config.yaml", 'r') as stream:
        try:
            parameters = yaml.safe_load(stream)
        except yaml.YAMLError as exc:
            print(f"[DEBUG] YAML error: {exc}")
            raise exc

    assert len(parameters['positions']) > 0
    assert len(parameters['locations']) > 0
    assert USERNAME is not None, "USERNAME environment variable not set"
    assert PASSWORD is not None, "PASSWORD environment variable not set"
    assert PHONE_NUMBER is not None, "PHONE_NUMBER environment variable not set"
    assert SALARY is not None, "SALARY environment variable not set"
    assert RATE is not None, "RATE environment variable not set"

    if 'uploads' in parameters.keys() and type(parameters['uploads']) == list:
        raise Exception("uploads read from the config file appear to be in list format" +
                        " while should be dict. Try removing '-' from line containing" +
                        " filename & path")

    log.info({k: parameters[k] for k in parameters.keys() if k not in ['username', 'password']})
    print(f"[DEBUG] Loaded parameters: { {k: parameters[k] for k in parameters.keys() if k not in ['username', 'password']} }")

    output_filename = [f for f in parameters.get('output_filename', ['output.csv']) if f != None]
    output_filename = output_filename[0] if len(output_filename) > 0 else 'output.csv'
    blacklist = parameters.get('blacklist', [])
    blackListTitles = parameters.get('blackListTitles', [])

    uploads = {} if parameters.get('uploads', {}) == None else parameters.get('uploads', {})
    for key in uploads.keys():
        assert uploads[key] != None

    print("[DEBUG] Instantiating EasyApplyBot")
    bot = EasyApplyBot(
        USERNAME,
        PASSWORD,
        phone_number=PHONE_NUMBER,
        salary=SALARY,
        rate=RATE,
        uploads=uploads,
        filename=output_filename,
        blacklist=blacklist,
        blackListTitles=blackListTitles,
        experience_level=parameters.get('experience_level', [])
    )

    locations = [l for l in parameters['locations'] if l != None]
    positions = [p for p in parameters['positions'] if p != None]
    print(f"[DEBUG] Starting bot.start_apply with positions: {positions}, locations: {locations}")
    bot.start_apply(positions, locations)
