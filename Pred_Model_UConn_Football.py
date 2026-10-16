"""UConn Football QB commitment fit predictor (Model 2).

Production-only version of the experimental script. Uses 2024-2025
FBS commitments to score 137 candidate schools. Scores are NOT probabilities.
The geographic Model 3 research is deliberately excluded.
"""
from pathlib import Path
import pandas as pd
import numpy as np

PROJECT_FOLDER = Path(r"C:\Users\UxVeg\OneDrive\Documents")
INPUT_FILE = PROJECT_FOLDER / "UCONNFOOTBALLPROJECT.xlsx"

ALL_STATES = {
    "AL":"Alabama", "AK":"Alaska", "AZ":"Arizona", "AR":"Arkansas",
    "CA":"California", "CO":"Colorado", "CT":"Connecticut", "DE":"Delaware",
    "FL":"Florida", "GA":"Georgia", "HI":"Hawaii", "ID":"Idaho",
    "IL":"Illinois", "IN":"Indiana", "IA":"Iowa", "KS":"Kansas",
    "KY":"Kentucky", "LA":"Louisiana", "ME":"Maine", "MD":"Maryland",
    "MA":"Massachusetts", "MI":"Michigan", "MN":"Minnesota", "MS":"Mississippi",
    "MO":"Missouri", "MT":"Montana", "NE":"Nebraska", "NV":"Nevada",
    "NH":"New Hampshire", "NJ":"New Jersey", "NM":"New Mexico", "NY":"New York",
    "NC":"North Carolina", "ND":"North Dakota", "OH":"Ohio", "OK":"Oklahoma",
    "OR":"Oregon", "PA":"Pennsylvania", "RI":"Rhode Island", "SC":"South Carolina",
    "SD":"South Dakota", "TN":"Tennessee", "TX":"Texas", "UT":"Utah",
    "VT":"Vermont", "VA":"Virginia", "WA":"Washington", "WV":"West Virginia",
    "WI":"Wisconsin", "WY":"Wyoming"
}


def load_model_data():
    if not INPUT_FILE.exists():
        raise FileNotFoundError(f"Cannot find recruiting workbook: {INPUT_FILE}")
    raw = pd.read_excel(INPUT_FILE, sheet_name="Full Data")
    raw.columns = raw.columns.str.strip()
    required = ["QB", "CLASS", "247 RATINGS", "STARS", "INCHES", "WEIGHT",
                "STATE", "ABB", "HIGH SCHOOL", "HIGH SCHOOL TIER",
                "COMMITTED SCHOOL", "FBS OR FCS", "PLAYER URL"]
    missing = sorted(set(required) - set(raw.columns))
    if missing:
        raise ValueError(f"Missing workbook columns: {missing}")
    for col in ["QB", "STATE", "ABB", "HIGH SCHOOL TIER", "COMMITTED SCHOOL", "FBS OR FCS"]:
        raw[col] = raw[col].astype("string").str.strip()
    raw["ABB"] = raw["ABB"].str.upper()
    raw["FBS OR FCS"] = raw["FBS OR FCS"].str.upper()
    for col in ["CLASS", "247 RATINGS", "STARS", "INCHES", "WEIGHT"]:
        raw[col] = pd.to_numeric(raw[col], errors="coerce")
    fbs = raw.loc[raw["FBS OR FCS"] == "FBS"].copy()
    fbs["SOURCE_ROW_ID"] = fbs.index
    # Match original Sections 2-4: remove conflicting QB/class commitments,
    # then deduplicate identical QB/class/destination combinations.
    counts = fbs.groupby(["QB", "CLASS"])["COMMITTED SCHOOL"].nunique()
    ambiguous = counts[counts > 1].index
    if len(ambiguous):
        mask = pd.MultiIndex.from_frame(fbs[["QB", "CLASS"]]).isin(ambiguous)
        fbs = fbs.loc[~mask].copy()
    fbs = fbs.drop_duplicates(subset=["QB", "CLASS", "COMMITTED SCHOOL"]).copy()
    # Retain original training-time Elite flag exactly as in Section 4.
    fbs["ELITE_HS"] = (fbs["HIGH SCHOOL TIER"] == "Elite").astype(float)
    history = fbs.loc[fbs["CLASS"].isin([2024, 2025])].copy()
    # The historical experiment used a retrospective candidate universe
    # based on all available FBS commitments, including 2026.
    schools = sorted(fbs["COMMITTED SCHOOL"].dropna().unique().tolist())
    if history.empty or not schools:
        raise ValueError("Insufficient historical data or candidate schools")
    for abb, state in history[["ABB", "STATE"]].dropna().drop_duplicates().itertuples(index=False, name=None):
        if abb in ALL_STATES and ALL_STATES[abb] != state:
            raise ValueError(f"State naming mismatch for {abb}: {state}")
    return history, schools

def create_qb_school_pairs(qbs, schools):

    # One row for each candidate school
    school_data = pd.DataFrame({
        "CANDIDATE SCHOOL": schools
    })

    # Cross join:
    # every QB gets paired with every candidate school
    pairs = qbs.merge(
        school_data,
        how="cross"
    )

    # Label the actual destination
    pairs["COMMITTED"] = (
        pairs["COMMITTED SCHOOL"]
        == pairs["CANDIDATE SCHOOL"]
    ).astype(int)

    return pairs

def build_school_profiles(history, candidate_schools):

    school_profiles = (
        history
        .groupby("COMMITTED SCHOOL")
        .agg(
            SCHOOL_PREVIOUS_QBS=("QB", "count"),
            SCHOOL_AVG_RATING=("247 RATINGS", "mean"),
            SCHOOL_AVG_HEIGHT=("INCHES", "mean"),
            SCHOOL_AVG_WEIGHT=("WEIGHT", "mean"),
            SCHOOL_ELITE_HS_PERCENT=("ELITE_HS", "mean")
        )
        .reset_index()
        .rename(
            columns={"COMMITTED SCHOOL": "CANDIDATE SCHOOL"}
        )
    )

    # Include schools with no previous QB commitments.
    school_profiles = pd.DataFrame({
        "CANDIDATE SCHOOL": candidate_schools
    }).merge(
        school_profiles,
        on="CANDIDATE SCHOOL",
        how="left"
    )

    school_profiles["SCHOOL_PREVIOUS_QBS"] = (
        school_profiles["SCHOOL_PREVIOUS_QBS"]
        .fillna(0)
        .astype(int)
    )

    return school_profiles

def add_school_fit_features(pairs, history):

    pairs = pairs.copy()

    profiles = build_school_profiles(
        history,
        fbs_school_list
    )

    pairs = pairs.merge(
        profiles,
        on="CANDIDATE SCHOOL",
        how="left",
        validate="many_to_one"
    )

    # Number of historical recruiting classes.
    historical_classes = history["CLASS"].nunique()

    if historical_classes > 0:
        pairs["SCHOOL_AVG_QBS_PER_CLASS"] = (
            pairs["SCHOOL_PREVIOUS_QBS"]
            / historical_classes
        )
    else:
        pairs["SCHOOL_AVG_QBS_PER_CLASS"] = 0.0

    # --------------------------------------------------------
    # RATING / PHYSICAL FIT
    # --------------------------------------------------------

    pairs["RATING_FIT"] = (
        pairs["247 RATINGS"]
        - pairs["SCHOOL_AVG_RATING"]
    ).abs()

    pairs["HEIGHT_FIT"] = (
        pairs["INCHES"]
        - pairs["SCHOOL_AVG_HEIGHT"]
    ).abs()

    pairs["WEIGHT_FIT"] = (
        pairs["WEIGHT"]
        - pairs["SCHOOL_AVG_WEIGHT"]
    ).abs()

    # --------------------------------------------------------
    # HIGH SCHOOL TIER FIT
    # --------------------------------------------------------

    tier_counts = (
        history
        .groupby(
            ["COMMITTED SCHOOL", "HIGH SCHOOL TIER"]
        )
        .size()
        .reset_index(name="TIER_COUNT")
        .rename(
            columns={
                "COMMITTED SCHOOL": "CANDIDATE SCHOOL"
            }
        )
    )

    pairs = pairs.merge(
        tier_counts,
        left_on=[
            "CANDIDATE SCHOOL",
            "HIGH SCHOOL TIER"
        ],
        right_on=[
            "CANDIDATE SCHOOL",
            "HIGH SCHOOL TIER"
        ],
        how="left"
    )

    pairs["TIER_COUNT"] = (
        pairs["TIER_COUNT"].fillna(0)
    )

    pairs["HS_TIER_FIT"] = (
        pairs["TIER_COUNT"]
        / pairs["SCHOOL_PREVIOUS_QBS"].replace(0, np.nan)
    )

    # --------------------------------------------------------
    # SCHOOL-STATE RECRUITING HISTORY
    # --------------------------------------------------------

    state_counts = (
        history
        .groupby(["COMMITTED SCHOOL", "STATE"])
        .size()
        .reset_index(name="SCHOOL_STATE_QBS")
        .rename(
            columns={
                "COMMITTED SCHOOL": "CANDIDATE SCHOOL"
            }
        )
    )

    pairs = pairs.merge(
        state_counts,
        on=["CANDIDATE SCHOOL", "STATE"],
        how="left"
    )

    pairs["SCHOOL_STATE_QBS"] = (
        pairs["SCHOOL_STATE_QBS"].fillna(0)
    )

    # Laplace-style smoothing:
    # Avoid treating zero historical observations as
    # absolute proof that a school will not recruit a state.

    state_market = (
        history["STATE"]
        .value_counts(normalize=True)
        .to_dict()
    )

    pairs["STATE_MARKET_SHARE"] = (
        pairs["STATE"]
        .map(state_market)
        .fillna(0)
    )

    smoothing_strength = 5.0

    pairs["STATE_PIPELINE_FIT"] = (
        pairs["SCHOOL_STATE_QBS"]
        + smoothing_strength
        * pairs["STATE_MARKET_SHARE"]
    ) / (
        pairs["SCHOOL_PREVIOUS_QBS"]
        + smoothing_strength
    )

    # --------------------------------------------------------
    # FINAL CHECK
    # --------------------------------------------------------

    if len(pairs) == 0:
        raise ValueError("No QB-school pairs remain.")

    return pairs

def smoothed_average(
    school_mean,
    school_count,
    global_mean,
    prior=5.0
):
    count = school_count.fillna(0)
    mean = school_mean.fillna(global_mean)

    return (
        mean * count + global_mean * prior
    ) / (count + prior)

def normalize_within_qb(data, column):

    group_min = data.groupby(
        "SOURCE_ROW_ID"
    )[column].transform("min")

    group_max = data.groupby(
        "SOURCE_ROW_ID"
    )[column].transform("max")

    denominator = group_max - group_min

    return (
        (data[column] - group_min)
        / denominator.replace(0, np.nan)
    ).fillna(0.0)

def score_model_2(pairs, history):

    data = pairs.copy()

    global_rating = history["247 RATINGS"].mean()
    global_height = history["INCHES"].mean()
    global_weight = history["WEIGHT"].mean()

    rating_counts = (
        history.groupby("COMMITTED SCHOOL")["247 RATINGS"]
        .count()
    )

    height_counts = (
        history.groupby("COMMITTED SCHOOL")["INCHES"]
        .count()
    )

    weight_counts = (
        history.groupby("COMMITTED SCHOOL")["WEIGHT"]
        .count()
    )

    for name, counts in [
        ("RATING_OBSERVATIONS", rating_counts),
        ("HEIGHT_OBSERVATIONS", height_counts),
        ("WEIGHT_OBSERVATIONS", weight_counts)
    ]:
        data[name] = (
            data["CANDIDATE SCHOOL"]
            .map(counts)
            .fillna(0)
        )

    data["SMOOTHED_RATING"] = smoothed_average(
        data["SCHOOL_AVG_RATING"],
        data["RATING_OBSERVATIONS"],
        global_rating,
        5.0
    )

    data["SMOOTHED_HEIGHT"] = smoothed_average(
        data["SCHOOL_AVG_HEIGHT"],
        data["HEIGHT_OBSERVATIONS"],
        global_height,
        5.0
    )

    data["SMOOTHED_WEIGHT"] = smoothed_average(
        data["SCHOOL_AVG_WEIGHT"],
        data["WEIGHT_OBSERVATIONS"],
        global_weight,
        5.0
    )

    data["RATING_COMPATIBILITY"] = np.exp(
        -(
            data["247 RATINGS"]
            - data["SMOOTHED_RATING"]
        ).abs() / 5.0
    ).fillna(0.5)

    height_score = np.exp(
        -(
            data["INCHES"]
            - data["SMOOTHED_HEIGHT"]
        ).abs() / 4.0
    )

    weight_score = np.exp(
        -(
            data["WEIGHT"]
            - data["SMOOTHED_WEIGHT"]
        ).abs() / 30.0
    )

    data["PHYSICAL_COMPATIBILITY"] = (
        0.5 * height_score
        + 0.5 * weight_score
    ).fillna(0.5)

    data["FREQUENCY_NORMALIZED"] = (
        normalize_within_qb(
            data,
            "SCHOOL_PREVIOUS_QBS"
        )
    )

    data["PIPELINE_NORMALIZED"] = (
        normalize_within_qb(
            data,
            "STATE_PIPELINE_FIT"
        )
    )

    # Same weights as Section 8.
    # Do not adjust them based on 2026 results.

    data["MODEL_2_SCORE"] = (
        0.25 * data["FREQUENCY_NORMALIZED"]
        + 0.40 * data["PIPELINE_NORMALIZED"]
        + 0.25 * data["RATING_COMPATIBILITY"]
        + 0.10 * data["PHYSICAL_COMPATIBILITY"]
    )

    if not np.isfinite(
        data["MODEL_2_SCORE"].to_numpy()
    ).all():
        raise ValueError("Invalid Model 2 scores.")

    return data

NUMERIC_PAIR_COLUMNS = [
    "CLASS", "247 RATINGS", "STARS", "INCHES", "WEIGHT", "ELITE_HS",
    "SOURCE_ROW_ID", "SCHOOL_PREVIOUS_QBS", "SCHOOL_AVG_RATING",
    "SCHOOL_AVG_HEIGHT", "SCHOOL_AVG_WEIGHT", "SCHOOL_ELITE_HS_PERCENT",
    "SCHOOL_AVG_QBS_PER_CLASS", "SCHOOL_STATE_QBS", "STATE_MARKET_SHARE",
    "STATE_PIPELINE_FIT", "RATING_FIT", "HEIGHT_FIT", "WEIGHT_FIT",
    "TIER_COUNT", "HS_TIER_FIT"
]


def predict_new_qb(name, state, height_inches, weight, rating=None, stars=None,
                   recruiting_class=2027, high_school="Unknown",
                   high_school_tier=None, top_n=10):
    abb = str(state).strip().upper()
    if abb not in ALL_STATES:
        raise ValueError("Use a valid two-letter US state abbreviation")
    if not 55 <= float(height_inches) <= 90:
        raise ValueError("Height should be in inches (55-90)")
    if not 100 <= float(weight) <= 350:
        raise ValueError("Weight should be in pounds (100-350)")
    # Build a single record using the same schema as historical training.
    new_qb = pd.DataFrame([{col: np.nan for col in history_2024_2025.columns}], dtype=object)
    values = {
        "QB": name, "CLASS": int(recruiting_class), "POSITION": "QB",
        "STATE": ALL_STATES[abb], "ABB": abb, "HIGH SCHOOL": high_school,
        "HIGH SCHOOL TIER": high_school_tier, "INCHES": float(height_inches),
        "WEIGHT": float(weight), "247 RATINGS": np.nan if rating is None else float(rating),
        "STARS": np.nan if stars is None else float(stars),
        "PLAYER URL": "NEW_RECRUIT_" + str(name).replace(" ", "_"),
        "SOURCE_ROW_ID": -1,
        # Match the validated Section 71 new-recruit implementation.
        "ELITE_HS": int(str(high_school_tier).strip().lower() == "elite hs")
    }
    for col, value in values.items():
        new_qb.at[0, col] = value
    for col in ["COMMITTED SCHOOL", "COMMITTED SCHOOL ID", "COMMITTED DATE",
                "STRAIGHT LINE DISTANCE (MILES)", "DRIVING DISTANCE (MILES)"]:
        if col in new_qb.columns:
            new_qb.at[0, col] = np.nan
    pairs = create_qb_school_pairs(new_qb, fbs_school_list)
    pairs = add_school_fit_features(pairs, history_2024_2025)
    for col in NUMERIC_PAIR_COLUMNS:
        if col in pairs.columns:
            pairs[col] = pd.to_numeric(pairs[col], errors="coerce").astype("float64")
    predictions = score_model_2(pairs, history_2024_2025)
    predictions = predictions.sort_values(
        ["MODEL_2_SCORE", "CANDIDATE SCHOOL"], ascending=[False, True]
    ).reset_index(drop=True)
    predictions["PREDICTED_RANK"] = np.arange(1, len(predictions) + 1)
    print("\nTOP UNIVERSITIES")
    print(predictions[["PREDICTED_RANK", "CANDIDATE SCHOOL", "MODEL_2_SCORE"]]
          .head(top_n).round(4).to_string(index=False))
    return predictions


def show_uconn_analysis(predictions):
    school_names = predictions["CANDIDATE SCHOOL"].astype(str)
    uconn = predictions.loc[school_names.str.fullmatch("UConn|Connecticut", case=False, na=False)]
    if uconn.empty:
        print("\nUConn was not found in the candidate university list.")
        return
    row = uconn.iloc[0]
    rank = int(row["PREDICTED_RANK"])
    print("\nUCONN RECRUITING FIT")
    print(f"Rank: {rank} / {len(predictions)} | Score: {row['MODEL_2_SCORE']:.4f}")
    print(f"Gap to top school: {predictions['MODEL_2_SCORE'].max() - row['MODEL_2_SCORE']:.4f}")
    features = ["SCHOOL_PREVIOUS_QBS", "SCHOOL_STATE_QBS", "STATE_MARKET_SHARE",
                "STATE_PIPELINE_FIT", "PIPELINE_NORMALIZED", "FREQUENCY_NORMALIZED",
                "RATING_COMPATIBILITY", "PHYSICAL_COMPATIBILITY", "SCHOOL_AVG_RATING",
                "SCHOOL_AVG_HEIGHT", "SCHOOL_AVG_WEIGHT"]
    for col in features:
        if col in predictions.columns:
            print(f"  {col}: {row[col]:.4f}" if pd.notna(row[col]) else f"  {col}: missing")
    nearby = predictions.loc[predictions["PREDICTED_RANK"].between(max(1, rank-3), rank+3)]
    print("\nSCHOOLS NEAR UCONN")
    print(nearby[["PREDICTED_RANK", "CANDIDATE SCHOOL", "MODEL_2_SCORE"]]
          .round(4).to_string(index=False))


def optional_number(prompt, convert=float):
    while True:
        raw = input(prompt).strip()
        if not raw:
            return None
        try:
            return convert(raw)
        except ValueError:
            print("Enter a valid number or leave blank.")


def required_number(prompt, convert=float):
    while True:
        value = optional_number(prompt, convert)
        if value is not None and value > 0:
            return value
        print("Enter a positive number.")


def run_interface():
    while True:
        print("\nQB RECRUITING PREDICTION MENU")
        print("1 - Predict a quarterback")
        print("2 - Exit")
        choice = input("Choose an option: ").strip()
        if choice == "2":
            print("Interface closed.")
            return
        if choice != "1":
            print("Choose 1 or 2.")
            continue
        name = input("Quarterback name: ").strip() or "Unnamed Quarterback"
        year = required_number("Recruiting class (e.g., 2027): ", int)
        while True:
            state = input("Home state abbreviation (e.g., MA): ").strip().upper()
            if state in ALL_STATES:
                break
            print("Enter a valid two-letter state abbreviation.")
        high_school = input("High school (optional): ").strip() or "Unknown"
        height = required_number("Height in inches: ")
        weight = required_number("Weight in pounds: ")
        rating = optional_number("247 rating (blank if unknown): ")
        stars = optional_number("Stars (blank if unknown): ", int)
        tier = input("High school tier (blank if unknown): ").strip() or None
        top_n = optional_number("Number of schools to display [10]: ", int)
        top_n = min(max(top_n or 10, 1), len(fbs_school_list))
        try:
            predictions = predict_new_qb(name, state, height, weight, rating, stars,
                                         year, high_school, tier, top_n)
            show_uconn_analysis(predictions)
            print("\nScores are relative school-fit scores, NOT probabilities.")
        except (ValueError, TypeError) as exc:
            print(f"Prediction could not be generated: {exc}")


if __name__ == "__main__":
    history_2024_2025, fbs_school_list = load_model_data()
    print("UCONN FOOTBALL - MODEL 2 QB RECRUITING FIT")
    print(f"Historical QBs: {len(history_2024_2025)}")
    print(f"Candidate universities: {len(fbs_school_list)}")
    print("All 50 US states supported. Geography not included.")
    run_interface()
