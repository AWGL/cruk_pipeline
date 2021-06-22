## overwrites the worksheet ID in each variables file so that basespace upload can be repeated
## by bashing the basespace cron
##
## Usage:
## bash within run directory with new worksheet ID as argument 
##    e.g. bash rename_ws.sh 21-123R


# throw error if no arguments provided
if [ -z "$1" ]
then 
    echo ERROR: Must input new worksheet ID
    exit 1
fi



# loop through variables file in each sample
for variables_file in */*.variables
do
    echo Updating $variables_file

    # get current WS and make line for new WS
    current_ws=$(grep worklistId= $variables_file | cut -f2 -d= | sed -e 's/^"//' -e 's/"$//')
    new_ws="worklistId=\""$1\"

    echo "  current:" $current_ws
    echo "  updated:" $1

    # throw warning if the new and old WS are the same
    if [ $1 == $current_ws ]
    then
        echo WARN: Inputed worksheet ID is the same as previous worksheet ID for $variables_file
    fi

    # make copy of variables file so we can pipe output of sed command below into original
    cp $variables_file $variables_file"_orig"

    # replace line in variables file
    sed "s/.*worklistId=.*/$new_ws/g" $variables_file"_orig" > $variables_file

done
