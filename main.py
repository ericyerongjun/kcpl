import shutil

from src.get_unzip_zip import unzip_iter
from src.extract_lectures import extract_lectures_from_course
from src.filter_convert import filter_and_convert_course


def main():
    total_courses = 0
    total_copied = 0
    total_summary = {"kept": 0, "converted": 0, "deleted": 0}

    for course_dir in unzip_iter():
        total_courses += 1
        print(f"\n{'='*60}")
        print(f"Processing {course_dir.name}")
        print(f"{'='*60}")

        # Step 1: Extract lecture files → outcourses/
        copied = extract_lectures_from_course(course_dir)
        total_copied += len(copied)

        # Step 2: Filter & convert the output for this course
        if copied:
            out_dir = copied[0].parent  # e.g. outcourses/COMP5113_20231
            s = filter_and_convert_course(out_dir)
            for k in total_summary:
                total_summary[k] += s[k]

        # Step 3: Delete the unzipped course folder to free storage
        shutil.rmtree(course_dir)
        print(f"  🗑 Deleted unzipped folder: {course_dir}")

    print(f"\n{'='*60}")
    print(f"Pipeline complete")
    print(f"  Courses processed : {total_courses}")
    print(f"  Lecture files     : {total_copied}")
    print(f"  PDFs kept         : {total_summary['kept']}")
    print(f"  Converted to PDF  : {total_summary['converted']}")
    print(f"  Deleted (other)   : {total_summary['deleted']}")


if __name__ == "__main__":
    main()
