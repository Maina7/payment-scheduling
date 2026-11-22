import axios from 'axios'

let cachedToken = null;
let tokenExpiry = null
 
const getMpesaBaseUrl = () => process.env.MPESA_BASE_URL 

export const getAccessToken = async() => {
    if(cachedToken && tokenExpiry && Date.now() < tokenExpiry-60000){
        return cachedToken;
    }

    const consumerKey = process.env.MPESA_CONSUMER_KEY;
    const consumerSecret = process.env.MPESA_CONSUMER_SECRET;
    const auth = Buffer.from(`${consumerKey}:${consumerSecret}`).toString("base64");
    const baseUrl = getMpesaBaseUrl();

    try{
        const response = await axios.get(
            `${baseUrl}/oauth/v1/generate?grant_type=client_credentials`,
            {headers: {Authorization: `Basic ${auth}`}}
        );
        cachedToken = response.data.access_token;
        tokenExpiry = Date.now() + response.data.expires_in * 1000;
        console.log("MPESA Token generated successfully");
        return cachedToken;
    }catch(error){
        console.error("Failed to generate MPESA access token", error.message);
        throw new Error("MPESA Authentication failed")
        
    }
}