# geo_microservice

### **API Endpoints**

1. **Search Endpoint** (**`/search`**):
    - Accepts query parameters for database, study types, sample types, platform, .etc.
    - For each search, the communication actually queries the GEO API twice, the first query will return the web_env and query key, and the second query will return the detailed information from the second query.
    - Search parameters are added to the path parameters, the whole search URL will be `/search/{database}&{term}` term can be combined. For example, if user wants to search GSE[ETYP] and GPL96[ACCN] the term would be “GSE[ETYP]+AND+GPL96[ACCN]”, and the operator can be OR or NOT, operators can be connected with these operators.
    - The results are stored in a MongoDB database with the web_env and data for further data manipulation. We will talk about the database part after this section.
2. **Filter Endpoint** (**`/filter`**):
    - Receives search results and filter criteria. Filter data are in the URL as well. The filter term is passed as a string in`/filter/{web_env}&{filter}`.
    - Applies filters and returns refined data. The data are retrieved from the database, previously from search results.
3. **Download Endpoint** (**`/download`**):
    - Users will have two options: download all returned result datasets or download one project based on the accession number
    - The download method will accept GEO project accession numbers.
    - The download-all method will return all the FTP addresses with corresponding accession numbers.
